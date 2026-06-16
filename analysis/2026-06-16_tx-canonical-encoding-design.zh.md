# 設計 — 交易規範化編碼與簽名(WP §2 conformance)

**日期:** 2026-06-16
**狀態:** 設計已核可(brainstorming),待出實作計畫。
**簇(B-3):** COW-1937、1942、1943、1944、1212、1215、1945。
**規格權威裁定:** 以實作的 **instruction(指令)模型**為權威;白皮書 §2 的平坦 Ethereum 式 tx
描述已過時,將被**重寫**為規範化 instruction-tx 形式。我們**不**把 tx 攤平成
`to/value/payload`。

---

## 0. 精煉(2026-06-16):編碼原語 = commonware-codec,非 CBOR

Plan 階段 grounding 發現:`Instruction`、`Block`、`Notarized`、`Actor`、`Message`、`Account`
等**早已用確定性、有序的 `commonware_codec::{Write, Read}` 二進位編碼**
(`node/types/src/execution.rs:1647` Instruction、`:4042` Block —— 後者即 `block_hash`/共識所建)。
**`Transaction` 是唯一例外**:其 `Write` 做 `ciborium::into_writer(self)` → serde-CBOR **map**
(`execution.rs:397`)。這個 serde-CBOR map 正是「map vs array / 非規範」缺陷的真正根因。

**裁定(取代下文 §4.1、§5、§4.6、§6、§11 的「CBOR」措辭):** 規範化編碼採**有序
`commonware-codec` 二進位編碼**,覆用 `Instruction` 既有的 `Write`/`Read`。把
`Transaction::{Write, Read, EncodeSize}` 改寫為 `Block` 已用的有序欄位模式(取代 serde-CBOR)、
加新欄位、簽名雜湊定義在此編碼上。WP §2 + Appendix A 改寫為描述**規範化 commonware-codec
二進位編碼**(非 CBOR)。如此消除異類、覆用整棵既有確定性 Instruction 編碼(無需逐變體重寫)、
並與全鏈其他共識編碼對齊。下文凡寫「CBOR 陣列」處,讀作「有序 commonware-codec 編碼」;§5.1 的
欄位順序與其他所有裁定不變。

---

## 0b. 審計修正(2026-06-16,折入 Marshal F1–F6)

獨立對抗式審計(Marshal,run #186)核實了確定性地基與編碼裁定 sound,但找到真實缺口。
解決(以下**取代**下文對應文字;node plan 實作之):

- **F1(critical)— `tx_hash` / `digest()` 須明確遷移。** 鏈上 tx 身份為
  `Transaction::digest() = keccak256(digest_preimage())`,而 `digest_preimage()` 現呼叫
  `payload_bytes()`(本工作要刪)+ 手動追加 deferred 額外位元組(`execution.rs:444-485`)。
  **解決:** `digest_preimage()` 改為交易的 canonical `encode()`、**所有簽名清零**(與
  `signing_hash` 同一 preimage)。如此(a)去除 `payload_bytes` 依賴,(b)`origin_*` 成內建
  canonical 欄位、手動 deferred 追加消失,(c)tx 身份保持**與簽名無關**(保留今日性質、並關閉
  ECDSA s-value 對身份的 malleability)。結果:`tx_hash == signing_hash`(同 preimage)。此取代
  §4.4 的「encode(full signed tx)」—— canonical preimage **排除**簽名。**漣漪:** Solidity bridge
  以 `keccak256(digest_preimage())` 重導 leaf(`execution.rs:446-448` 註)→ 其 leaf 重導須改用
  canonical 編碼器;列為跨倉協調項(devnet flag-day,bridge 多半未上線)。

- **F2(high)— cli + node 的 runner message-to-sign 端點屬本計畫範圍。** 刪
  `payload_bytes`/`payload_hash` 會打斷同工作區呼叫方:`node/cli/src/commands.rs` 簽名,與
  **`node/rpc/src/handlers/runner.rs`**(`heartbeat_payload_hash` `:273`、`message-to-sign`
  端點 `:882+`)—— node 發給 runner 簽的 hash。這些是 node 內部,**本計畫**內須遷到
  `signing_hash()`(非 follow-on),否則 runner/heartbeat tx 過不了 `verify()`。

- **F3(high)— 真實邊界的嚴格拒尾位元組。** 生產解碼是
  `Submission::read(&mut body.as_ref())`(`node/rpc/src/handlers/chain.rs:221`)。
  `commonware_codec::Read::read_cfg` **不**檢查緩衝結尾;只有 `Decode::decode` 檢
  (`Error::ExtraData`)。**解決:** 提交邊界須用會檢結尾的 decode(或斷言 `remaining()==0`)並拒
  尾位元組;測試打真實 `Submission`/admission 路徑,非虛構 helper。

- **F4(medium)— plan 片段更正:** `recover_address` 回 `Result`(配 `Ok(..)` 非 `Some(..)`);
  `keccak256` 在 types crate 內裸呼叫/`crate::`(非 `cowboy_types::`);
  `Vec<(Address, Vec<[u8;32]>)>`(access_list)與 `Vec<(Address, EthSignature)>`
  (additional_signers)的 codec 是**全新**(無既有模板可抄 —— 它們過去藏在整 tx 的 serde-CBOR
  blob 內)。

- **F5(med/low)— WP 範圍 + 界限。** WP 重寫須一併修 **WP line 198 的獨立 normative MUST**
  (跨信任邊界資料 MUST 用 canonical CBOR,RFC 8949)與 **§2.2(d)**(access-list 無效⇒拒)——
  不只 §2/Appendix A。`MAX_TRANSACTION_BYTES` 現於長度前綴的 `Transaction::read` 內強制;前綴去除
  後須改置於提交邊界。

- **F6(low)— 準確性。** `is_deferred()` **純為 `origin_tx_hash.is_some()`**
  (`execution.rs:277`)。**chain_id `None` 裁定:** genesis `chain_id` 為 `Option<u64>` 預設
  `None`;devnet **在 genesis 釘一個具體 devnet `chain_id`**、客戶端用之,admission 拒任何不符
  (非測試配置無「accept-any」模式)。(見 R3 —— 須為有序啟用步驟,非隱形前提。)

---

## 0c. 第三輪深度審計修正(2026-06-16,Marshal run #188 — block 須修)

第三輪更深審計走訪前兩輪假設乾淨的 **`Instruction` 葉子型別**,發現核心反 malleability 不變量
(§4.1:每筆 tx 恰一規範編碼、`decode∘encode==id`)對覆用的 codec **為假**。以下實作前 MUST-FIX:

- **R1(CRITICAL)— `Instruction` codec 在 `Custom` 上非單射。** `Instruction::Write` 對
  `Custom{module,action,data}` 把 `module` **原樣**寫出(`execution.rs:2554`),但 `Read` 以該首
  byte 分派(`0→System,1→Actor,3→Library`,否則 `Custom`,`:3348`)。故
  `Custom{module:0,action:0,data:<20 bytes>}` 編碼**等同** `System(CreateAccount)`,且
  `decode(encode(Custom{0}))=System` 非 identity。舊 serde-CBOR map 在此**是單射**(欄位名為鍵)→
  改用即為**回歸**;且**未測**(round-trip 只用 `module:5`)。**解決(plan 內裁):** 或(a)讓 codec
  單射 —— `Custom::write` 釘 category byte(`TX_CATEGORY_CUSTOM=2`)、`module` 入 body,`Read` 以
  `2`→`Custom`(先 grep 確認 blast radius:`Instruction` 只經 `Transaction`→`Block.transactions`
  進共識,則本 flag-day 內含);或(b)保留 codec 但 **admission/構造時拒 `Custom{module∈{0,1,3}}`**
  並把 §4.1 不變量**範圍縮到 admission-valid tx**。兩者皆須加 `module∈{0,1,2,3}` round-trip 測試。
  若 grep 證 `Instruction` 僅 tx-only,預設取(a)。

- **R2(HIGH)— `Constraints` bool 欄位非嚴格。** `Constraints`(`entitlement.rs:262`,由
  `EntitlementGrant/Delegate/CreateRole` 攜帶)寫 `(self.delegatable as u8)`、讀 `u8::read()? != 0`
  (`:326/367`),故 `0x02` 解 `true` 再編 `0x01` —— `encode∘decode != id`,用戶 tx 可達的 malleability。
  **修:** 嚴格 bool 解碼。

- **R3(HIGH,ops/liveness)— genesis `chain_id` flag-day 陷阱。** `chain_id` 除 local-setup 外處處
  預設 `None`。若啟用上了 `tx.chain_id != node_chain_id` 檢查而 genesis 仍 `None`(且 `None` 當具體值)
  → **每筆 tx 被拒 → 鏈停**。**解決:** 把「更新 genesis `chain_id` 到釘定值」升為啟用 runbook(§7)的
  **明確、第一、阻塞**步驟;非測試配置 `None` ⇒ **啟動硬失敗**(絕不靜默 accept-any,否則防重放失效)。

- **R4(文檔,wallet/SDK 位元組相容 MUST)— §4.1 具體規則具誤導性。** §0 的「CBOR 讀作 commonware-codec」
  **不**中和 §4.1 的具體規則,wallet/SDK 實作者會照字面做。§4.1 的「definite-length CBOR array」、
  「minimal-length 整數」、「Option=CBOR null」對 commonware-codec **全錯**,實為:**扁平串接**(無陣列
  外層);**混合整數** —— bare `u64`(chain_id/nonce/gas)用最小 **varint(`UInt`)**、`u128` 金額與
  `Option<u64>` 用**固定大端**;**`Option` = `bool`(0/1)tag + 值**(非 null);位元組串 = **varint 長度 +
  位元組**。下文 §4.1 已據此更正,且 **TV fixture(§4.5)為位元組權威**。`ciborium vs 手寫` 的開放項
  (§4.1/§11)刪除 —— 原語已定(commonware-codec)。

- **R5(測試)— `EncodeSize` 精確。** 手寫的 17 欄 `Transaction::EncodeSize` 須精確等於 `Write` 位元組
  長度,否則 commonware-codec 誤算緩衝。加 `assert_eq!(tx.encode_size(), tx.encode().len())` 測試。

**第三輪核實 solid(無須動作):** 有界 `Vec` 解碼在**配置前**拒超界長度(無 decode-bomb);`UInt` 嚴格
最小;覆用的 `Instruction::EncodeSize` 與 `Write` 相符;所有 tx 可達葉子型別確定性(CBSS 固定大小;
`ActorManifest` 用排序 `BTreeMap` 非 `HashMap`;無浮點);deferred preimage 遷移一致且 devnet 重置
**確有必要**(否則 flag-day 前的 `origin_tx_hash` 會過不了 parent-receipt 檢查)。

---

## 0d. 第四輪窮盡式審計修正(2026-06-16,Marshal run #189)

第四輪在 round 3 抽樣處改為**窮盡** —— 列舉每個 tx 可達 enum 與 bool。結論:規範不變量
**靠少數可枚舉的點修 + 一條語義規則即可達成**(非系統性 codec 問題)。R1/R2 之外的新 MUST-FIX:

- **R6(HIGH)— R2 漏掉的第二個非嚴格 bool。** `SystemInstruction::RunnerUpdateDelegationConfig.accept_delegation`
  寫 `if{1u8}else{0u8}`(`execution.rs:2058`)、讀 `u8::read()? != 0`(`:2845`)—— opcode 119、
  用戶可提交;`0x02`→`true`→再編 `0x01`。R2 只修了 `entitlement.rs` 的 `Constraints`;此 `execution.rs`
  站點相同。**修:** 同 `match {0,1,_=>Err}`。(同 impl 內約 6 個兄弟 bool **是**嚴格的 —— 不一致複製
  風險;R10 的測試須機械化抓出其餘。)

- **R7(HIGH)— `additional_signers` 無規範順序或唯一性。** `verify()`(`execution.rs:346`)按儲存
  順序迭代 `additional_signers`、僅檢每個 `(addr,sig)` 復原為 `addr`;**不檢順序也不去重**,且
  `all_signer_addresses()`(`:100`)順序相關。故同一 signer 集的兩種順序、或補重複有效項 → 一個邏輯
  授權產生**不同 `tx_hash`/`signing_hash`** = tx 身份 malleability。**此洞在 `verify()` 非 codec**,
  故聚焦 codec 的 1-3 輪結構上抓不到。**修:** 要求 `additional_signers` **按地址排序且無重複**
  (否則 `verify()`/admission 拒)+ `MAX_ADDITIONAL_SIGNERS` 界限。

- **R8(MEDIUM)— `SessionVoucher` 簽名 pad/truncate 非單射。** `session.rs:156` write 時把
  `signature` pad/截到 `VOUCHER_SIGNATURE_LEN`、read 恆產該長度,故短/長補的 voucher 解碼時正規化
  (`encode∘decode != id`)。經 `SessionSettle`(op 54)/`SessionSlash`(op 57)tx 可達。**修:**
  decode/構造時拒 `signature.len() != VOUCHER_SIGNATURE_LEN`。

- **R9(MEDIUM,plan)— `METADATA_CFG` 下界。** `metadata` 的 `RangeCfg` 上界須 **≥ 最大 CIP-29
  envelope(~6.4 KB)**,否則系統 event-fire 的 **deferred** tx 解不出。須精確釘(非「open」)。

- **R10(測試強制)— 窮盡 round-trip。** conformance round-trip 測試須迭代**每個 `SystemInstruction`
  opcode 與每個 tx 可達巢狀 enum**(非只 `Custom` module)—— 唯一能機械化保證無其餘 `!=0`/catch-all
  殘留的方法。

- **(LOW)** CIP-29 `EmitOrigin::from_metadata_bytes` 忽略尾位元組(`:563`)—— 僅縱深防禦(CIP-29 走
  node 自建的 deferred/system tx;非 tx-canonical 破口)。

**第四輪確認、第五輪更正(B5):** `Instruction` 經 `Transaction` 進共識,而 `Transaction` 進共識有
**兩個面** —— `Block.transactions`(→ `tx_root`/`block_hash`)**與 `StateValue::DeferredTx`
(`storage/state_value.rs:319`)→ `state_root`**(receipt 只存 `tx_type:u8` 非整個 `Instruction`)。
兩者皆在 devnet flag-day 重置,故 **plan Task 2b 路徑 (a)—— 改 `Custom` 編碼 —— 仍安全**;但表面清單為
`{tx_root, block_hash, state_root}`,且 **R10 round-trip 測試須涵蓋包在 `StateValue::DeferredTx` 內的
`Transaction`**。又:因 F1 使 `tx_hash`/`digest` **與簽名無關**,
`EthSignature` 的 `v`/s-malleability 皆無法 fork tx 身份(設計在此軸完全成立)。窮盡核實乾淨的 enum:
所有 `SystemInstruction`/`ActorInstruction`/`LibraryInstruction` 子分派(`_ => Err(InvalidEnum)`)、
`Scope`/`Action`、所有 `cbss` enum、`SessionAsset`、`Submission`/`UpdatesFilter`、葉子原語
`Address`/`EthSignature`/`Digest`。

---

## 1. 問題

白皮書 §2(cowboy-technical-whitepaper.md,461–493 行,normative)把交易定義為平坦的 13 元素
有序 CBOR 陣列
`[chain_id, nonce, to, value, cycles_limit, cells_limit, tip×2, access_list, payload, signature]`,
簽名雜湊 `keccak256(CBOR(Tx_without_signature))`。實作
(`node/types/src/execution.rs`)在每一軸都背離:

1. **模型。** `to`/`value`/`payload` 被折進帶型別的 `Instruction` enum
   (`System | Actor | Custom | Library`,有自己的 `TX_CATEGORY_*` wire opcode)。這個模型是
   刻意設計且更豐富(系統指令、deploy、library、multi-call);攤平會是嚴重退步。
2. **編碼。** `Transaction::write` 做 `into_writer(self)` → serde-CBOR **map**(欄位名為鍵),
   非有序陣列。
3. **簽名。** 簽名雜湊是對一個**獨立的 `PayloadSign` 子集 struct** 計算
   (`Transaction::payload_bytes`),非對真實交易。子集會與 wire tx 悄悄漂移(往 `Transaction`
   加欄位卻沒加到 `PayloadSign` → 該欄位未簽、可被竄改)。(COW-1944)
4. **重放。** 簽名負載中**無 `chain_id`**(genesis 帶 `chain_id: Option<u64>` 但 tx 沒有),
   故一筆已簽 tx 可跨鏈/跨 fork 重放。(COW-1212)
5. **access_list。** tx 中不存在;審計票稱其驗證為「空 stub」。(COW-1215)

**語境:** 這是 **devnet**(genesis 可配置 `chain_id`、deploy-to-dev CI)。沒有上線的 mainnet
交易流需要向後相容,故遷移可以是單一協調的 flag-day / devnet 重置,而非雙格式過渡。

---

## 2. 裁定(鎖定)

| # | 裁定 | 理由 |
|---|---|---|
| D1 | **instruction 模型權威;重寫 WP §2 + Appendix A** 描述規範化 instruction-tx。 | instruction 模型是核心且更優;退回平坦 `to/value/payload` 會摧毀 系統/deploy/library/multi-call。 |
| D2 | **`access_list` 保留為可選、領諮/保留欄位;v1 不強制。** WP 文檔註明保留給未來並行調度/預取。 | 指令本身已具名目標;Cowboy 無 EVM access-list gas 機制。強制驗證是大共識面、現無收益。空 stub 變成明確設計選擇而非 bug。 |
| D3 | **乾淨斷裂 flag-day / devnet 重置。** 單一啟用點;node + 所有 tx 生產端一起切;無雙格式碼。 | devnet ⇒ 無 tx 向後相容負擔。最簡、最少碼。 |

---

## 3. 範圍

**納入(v1):**
- COW-1937 — 規範化欄位集(真實 instruction-tx 欄位,凍結順序)。
- COW-1942 — 確定性有序陣列 CBOR 編碼(取代 serde map)。
- COW-1943 — `to`/`value` 留在 `Instruction` 內(由 D1 解決);新增可選 `access_list`。
- COW-1944 — 簽名雜湊取 `canonical(tx 去簽名)`;刪除 `PayloadSign`。
- COW-1212 — `chain_id` 入簽名負載 + admission 驗證。
- COW-1215 — `access_list` 語義(由 D2 解決:可選領諮)。
- COW-1945 — 凍結 conformance 測試向量(TV1 未簽、TV2 已簽)。

**排除(明確推到姊妹 spec,保持單一目的):**
- COW-1941 — Header/Block 規範化陣列編碼。動 `block_hash`(獨立共識面)。覆用本設計的
  canonical-codec;phase-2 姊妹。
- COW-1934 / 1935 — `python_source` canonicalization(UTF-8/NFC/LF/no-BOM)與 CREATE2 式
  actor 地址推導。屬相關「canonicalization」主題但與 tx 編碼獨立。
- COW-1753 — CIP-17 帳戶樹綁定 state-read proof。無關。

---

## 4. 單元(單一職責、可獨立測試)

### 4.1 `canonical` codec — `node/types/src/canonical.rs`(新)
- **職責:** 確定性 bytes ↔ `Transaction`。
- **介面:** `encode(tx: &Transaction) -> Vec<u8>`;`decode(bytes: &[u8]) -> Result<Transaction, CodecError>`。
- **編碼規則(commonware-codec;依 R4 更正 —— 非 CBOR):**
  - 交易欄位依 §5.1 **凍結順序**做**扁平串接** —— **無陣列外層**(commonware-codec 欄位首尾相接)。
  - **混合整數編碼(須與既有 impl 完全一致):** bare `u64`(`chain_id`、`nonce`、gas/fee)用最小
    **varint `UInt`**;`u128` 金額與 `Option<u64>` 用**固定大端**;集合長度用 varint。
  - `Option<T>` = **`bool`(0x00/0x01)tag 後接值(若有)** —— 非 CBOR null。`Vec<T>`/位元組串 =
    **varint 長度前綴 + 元素/位元組**。
  - 無浮點;無不定長;每個整數/`bool` 唯一嚴格形(`UInt` 拒非最小;`bool` 須拒 ∉{0,1} —— 見 R2)。
  - **TV fixture(§4.5)為位元組權威**;客戶端複製它,非照這些 bullet 的字面。
  - `Instruction` 編為自己的確定性子陣列 `[category, sub_type, body]`,與既有 `tx_type()`
    opcode 方案一致(讓型別 enum 有穩定規範 wire 形)。`body` 是所選 variant 欄位的遞迴確定性編碼。
  - `Option<T>` 編為 CBOR `null`(缺)或值(在)。`Vec<T>` 為 definite-length 陣列。
  - **確定性規則遞迴套用**到每一個巢狀結構(指令 body 及其子欄位、`access_list` 條目、
    `additional_signers` 條目),使整棵交易樹恰有唯一規範位元組形。
- **嚴格解碼(反 malleability,共識關鍵):** `decode` 必須**拒絕**(不正規化)任何非規範輸入:
  非最小整數、不定長項、陣列後尾位元組、元素數錯、重複或非預期結構。**不變量:** 每筆
  `Transaction` 恰有一個合法位元組編碼,且對所有規範 `b`,`decode(encode(tx)) == tx`、
  `encode(decode(b)) == b`。
- **原語層(已定,R4):** 既有 `commonware-codec` `Write`/`Read` —— 無新 CBOR 層、無 `ciborium`。
  覆用 `Instruction` 的 impl,`Transaction` 欄位編碼照 `Block::write` 同一慣例寫。

### 4.2 `chain_id` 欄位 + admission 驗證
- 往 `Transaction` 加 `chain_id: u64`(§5.1)。客戶端從 node 的 genesis `chain_id` 取。納入
  canonical 編碼與簽名雜湊。
- **Admission:** 拒 `chain_id != node.chain_id` 的 tx,回新結構化錯誤(如
  `E_TX_WRONG_CHAIN_ID`)。錯誤碼進 receipt/StructuredError 路徑,故共識相關。

### 4.3 signing-hash 函式(取代 `payload_bytes`/`payload_hash`/`PayloadSign`)
- `signing_hash(tx: &Transaction) -> [u8; 32]` = `keccak256(canonical_encode(tx'))`,其中 `tx'`
  為:主 `signature` 設 `EthSignature::ZERO`、每個 `additional_signers[i].1`(簽名)清零,而
  **signer 地址(`from`、`additional_signers[i].0`)保留**(讓簽名負載仍綁定 signer 集、防跨帳號
  重放 —— 保留現有性質)。
- 多簽:每個 signer 簽**同一個** `signing_hash`。
- **deferred 交易**(`is_deferred()`:nonce=0、`signature == ZERO`、`origin_remaining_*` 在)是
  **系統再注入、從不經用戶簽名**;其真實性續由 `verify()` 的 `origin_remaining_*` 界定檢查強制。
  canonical 編碼仍含 `origin_*` 欄位以保 `tx_hash` 確定,但 signing-hash/`ecrecover` 路徑只對
  非 deferred tx 走。

### 4.4 `tx_hash`
- `tx_hash(tx) = keccak256(canonical_encode(完整已簽 tx))` —— 全程同一 canonical 形(admission、
  mempool 鍵、receipts、block tx-root)。

### 4.5 conformance 測試向量 — 共享 fixture
- `TV1`(未簽:簽名 null)與 `TV2`(已簽),對一筆代表性 instruction tx(如 `System(Transfer)` 到固定
  地址、固定 gas),釘為小寫 hex。
- 以共享 JSON fixture 存一份(如 `refs/common/tx-canonical-vectors.json` 或 node 與 wallet 都能取的路徑),由下列消費:
  - node conformance 測試(`canonical_encode(TV 輸入)` == 釘住 hex;`signing_hash(TV2)` == 釘住雜湊),
  - wallet 位元組相容測試(§6)。
- 這些向量**取代** WP Appendix A 的平坦模型向量。

### 4.6 WP 重寫 — `cowboy/docs/whitepaper/cowboy-technical-whitepaper.md`
- 重寫 §2(Transaction Types & Encoding)與 Appendix A 描述 **instruction-tx** 規範形:凍結欄位
  陣列(§5.1)、`Instruction` 子編碼、簽名雜湊規則、`chain_id`、`access_list` 作為保留/領諮。
  編碼節維持 **normative**;Appendix A 向量變 normative 且與共享 fixture 一致。

---

## 5. 規範化交易形

### 5.1 凍結欄位順序(canonical 陣列)
canonical 編碼是這些元素**依此順序**的 definite-length 陣列(順序是規格一部分,非新 tx 格式版本
不得改):

```
[ chain_id,
  nonce,
  instruction,                    # 子陣列 [category, sub_type, body]
  cycles_limit,
  cells_limit,
  max_fee_per_cycle,
  max_fee_per_cell,
  max_priority_fee_per_cycle,
  max_priority_fee_per_cell,
  from,                           # 20 位元組地址
  access_list,                    # null | [[address, [storage_key,...]], ...]
  metadata,                       # 位元組串(可空)
  origin_tx_hash,                 # null | 32 位元組(僅 deferred)
  origin_remaining_cycles,        # null | u64(僅 deferred)
  origin_remaining_cells,         # null | u64(僅 deferred)
  signature,                      # 65 位元組;TV1 / deferred 為 ZERO
  additional_signers ]            # [[address, signature], ...](可空)
```

註:
- `to`/`value` **非**頂層 —— 在 `instruction` 內(如 `System(Transfer{to, amount})`),依 D1。
- `access_list` 在但 v1 為 `null`(D2)。
- deferred-only 欄位(`origin_*`)對一般用戶 tx 為 `null`。

### 5.2 簽名 vs 雜湊
- **簽名雜湊:** `keccak256(canonical_encode(tx 之 signature=ZERO 且所有 additional_signers 簽名清零;
  地址保留))`。
- **tx_hash:** `keccak256(canonical_encode(完整 tx))`。

---

## 6. 跨倉協調

改編碼/簽名/`tx_hash` 漣漪到**每一個交易生產端**,皆須輸出位元組相同的 canonical 編碼:

| 倉 | 元件 | 工作 |
|---|---|---|
| node | `types`(encode/sign/verify/admission) | 核心變更 |
| wallet | JS 簽名器(`window.cowboy`、tx 編碼器) | **最高風險** —— 用 JS 重實作確定性 CBOR 陣列 + keccak,與 node 位元組相同 |
| node/cli | tx builder | 切 canonical 簽名 |
| pvm/SDK(python) | 任何客戶端側 tx 構造 | 切 canonical 簽名 |
| runner | result/job tx 提交(若有構造 tx) | 切 canonical 簽名 |

**位元組相容機制:** 共享 TV fixture(§4.5)為唯一真相;node 與 wallet 各跑測試斷言其編碼器重現
釘住 TV hex 與簽名雜湊。任一邊不符即 build 失敗。

---

## 7. 遷移 / 啟用(flag-day)

1. node PR 先落 devnet(先加法、後切換),掛在 flag-day 後。
2. 客戶端 PR(wallet/cli/SDK/runner)落地,使生產端輸出新格式。
3. 協調**單一啟用** —— devnet 重置或啟用高度 —— 屆時 node 強制 canonical 編碼 + `chain_id` +
   新簽名雜湊,且所有客戶端已在輸出。無雙格式窗。
4. 發一份簡短 rollout runbook(順序、誰切什麼、rollback = 還原到重置點)。共識 PR 的 Marshal 判決
   會是 **needs_human**(tx_hash/state-root 變更)—— 預期;runbook 即協調 artifact。

---

## 8. 測試與 conformance 不變量

| 不變量 / 測試 | 斷言 |
|---|---|
| `contract.tx_canonical_roundtrip` | `encode→decode→encode` 位元組相同;`decode` **拒** 5 類非規範(非最小整數、不定長、尾位元組、元素數錯、子結構畸形)。 |
| `contract.tx_signing_hash_vector` | `signing_hash(TV2 輸入)` == 釘住雜湊;`canonical_encode(TV1)` == 釘住 hex。 |
| `contract.tx_chain_id_replay` | `chain_id != node.chain_id` 的 tx 在 admission 被拒。 |
| wallet 位元組相容測試 | wallet 編碼器重現共享 TV hex + 簽名雜湊。 |
| 既有 tx/簽名/mempool/econ 套件 | 維持綠(回歸)。 |

以上全走 Marshal 不變量門禁。因動 `tx_hash`/`state-root`,共識 PR 為協調上線(needs_human)。

---

## 9. PR 序列(各可獨立審查)

1. **PR1(node):** `canonical` codec 模組 + golden round-trip + malleability 測試。純加法(平行
   編碼器),零行為變更。
2. **PR2(node):** 往 `Transaction` 加 `chain_id` + `access_list` 欄位;納入 canonical 編碼;
   admission 驗 `chain_id`。(共識:tx shape 變更。)
3. **PR3(node):** wire 編碼 + 簽名雜湊 + `tx_hash` 全切 canonical;刪 `PayloadSign`;啟用嚴格解碼;
   釘 TV1/TV2 conformance 測試。(共識:flag-day 主變更。)
4. **PR4(wallet):** JS canonical 編碼器 + keccak;對共享 TV 位元組相容測試。
5. **PR5(cli / SDK / runner):** tx 構造切 canonical 簽名。
6. **PR6(cowboy docs):** 重寫 WP §2 + Appendix A 為 normative instruction-tx 編碼。
7. **啟用:** 跨倉協調 devnet 重置 / flag-day。

---

## 10. 風險與緩解

| 風險 | 緩解 |
|---|---|
| Wallet JS 位元組相容(確定性 CBOR 易微錯) | 共享 TV fixture + 雙邊相容測試;node 先發向量。 |
| 嚴格規範決定論(所有節點對任意位元組串須一致 accept/reject) | 手寫嚴格解碼 + 5 類 malleability 測試套件;不「正規化後接受」。 |
| 跨 6 PR / 4 倉的共識啟用 | 明確 PR 排序 + rollout runbook + flag-day;revert = 重置點。 |
| deferred-tx 欄位非用戶簽名 | sign/verify 路徑依 `is_deferred()` 分流;canonical 編碼仍含 `origin_*` 保 `tx_hash` 確定。 |
| 範圍蔓延到 Header/Block(1941)或地址推導(1934/1935) | 明確排除;姊妹 spec 覆用 codec。 |

---

## 11. 留給實作計畫的開放項(非設計阻塞)
- ~~嚴格確定性 codec 的 CBOR 原語層選型~~ —— 已定(R4):覆用 `commonware-codec`(非 CBOR)。
- 共享 TV fixture 最終路徑(node 與 wallet 都能取)。
- `chain_id` mismatch 的最終錯誤碼 slug/編號(遵四段式錯誤格式,COW-386)。
