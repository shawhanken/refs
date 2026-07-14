# Cowboy CIP 與白皮書 — 深度審計最終報告

> **📌 狀態(2026-07-13):後續處理 campaign 已落地。** 8 個 spec-reconciliation PR 全數 MERGED 進 `origin/main`(#241/#243/#247/#248/#249/#250/#251/#252,含 §5/§6/§9 及 §3 主 drift 群 CIP-4/24/12/16/2 + 三 WP;詳見 §13 ledger)。前期 15 HIGH + top-5 亦已閉環(#239/#240/#1004-1006/#1008/#1009/#1011)。**待團隊 decision(OPEN,2026-07-14 複核未變):** #236(CIP-30/27 fork)、#238(MIN_PROXY_STAKE)、#253(CIP-31 fee split 10/2/88→10/1/89);#237 已 closed。**單一 CIP 零星 LOW/MED 長尾:2026-07-14 起接手處理(§14),同法一 agent/CIP 抽 devnet ground truth → 四分類 → spec 修。**_

_多代理獨立審計,2026-07-09/10。兩趟工作流:(1) 39 份文件逐份獨立審計 + 確定性碰撞掃描 + 6 個主題跨文件代理 + 對 HIGH/CRITICAL 的雙視角對抗驗證;(2) 對 334 條 MEDIUM/LOW 發現補跑雙視角驗證。共 ~1,211 個子代理、~44.8M token。技術識別碼、`檔案:行號`、常量名、opcode 一律保留原文。_

## 1. 摘要

- **審計文件:** 39 份(34 份 CIP + 5 份白皮書文件)。
- **確認發現 312 條**,均經兩個獨立對抗驗證者(健全性視角 + 代碼落地視角,兩者都必須確認)通過。依「校正後嚴重度」分佈:**HIGH 15 · MEDIUM 170 · LOW 124 · INFO 3**。
- **依維度:** 規格↔代碼**漂移 123** · 一致性 71 · 完整性 87 · 安全 31。
- **對抗階段駁回:** 134 條候選被反駁丟棄(63 條 HIGH 層 + 71 條 MED/LOW)。另有 50 條驗證者意見分歧(需人工裁定,含數條 CRITICAL/HIGH 安全項)。
- **核心結論:** 規格已與上鏈代碼**系統性脫節**——312 條確認中 123 條是漂移。常量、opcode 編號、系統 actor 地址、record schema、費用計價單位、error 語義,在 CIP/白皮書與 node/runner/cbfs/cbss 之間全線對不上。**照數份規格原文獨立實作出的 client 會使鏈分叉。**

### 最嚴重的 5 項(附 2026-07-12 當前狀態)

> 下列是審計當時的 top-5;經後續處理與**回一手源核實**,4 項已閉環、第 5 項核出精確殘留。

1. **[cip-3-fee-model]** §2.2.3 lane budget 表 8× 錯(10M vs 上鏈 80M)。 → ✅ **已修**(H-6,規格改 80M,#239 merged)。
2. **[cip-31-cbfs-rent-schedule]** 儲存費計價 per-MiB vs per-byte ~23,301× + 拆分 10/1/89 vs 10/2/88。 → ✅ **兩部分全解**:拆分改 10/2/88(#239+#240 merged);**計價核實已解決**——devnet 代碼(`cowboy-protocol-types@0aa46e1`)`STORAGE_FEE_PER_MIB_PER_EPOCH = 450` 恰=規格,per-byte 常量全刪(#237 已 close)。*審計此條基於陳舊 base,實際代碼早已 per-MiB。*
3. **[cip-13-runner-delegation]** `MIN_SELF_BOND_BPS` 定義卻零強制。 → ✅ **已修**(H-1 代碼 #1004 merged + increase 路徑測試 #1006 merged)。
4. **[cip-8-mpp-session]** §12 謊稱 session handler 無 opcode(實為 52–57)。 → ✅ **規格已修**(#239 merged);**opcode 碰撞核實已被編譯期守衛覆蓋**:codec `Read for Instruction` 上 `#[deny(unreachable_patterns)]` + 字面量 decode arm(`52 =>`…`57 =>`),任何撞號=編譯錯。node 手工 `sys_opcode_uniqueness` list 漏 52–57 屬冗餘檢查的完整性小缺、**無實際暴露**(可選補列)。
5. **[cip-3-fee-model]** 4096-bit 整數守衛可繞過。 → ⚠️ **規格已誠實化(MUST→SHOULD,#239 merged);但運行期殘留經實測確認**:守衛是純 Python preamble(`_builtins.int = _GuardedInt`,只覆寫算術運算子、對**結果** `_check()`)。**construction 不檢查 + `pow()` builtin 未 rebind** → 實測 `int.from_bytes(4809-bit)`、`int("9"*2000)`、`pow(2,10000)` **全部繞過**(control `int(2)**10000` 正常被擋)。性質:**確定性(全 validator 一致→無分叉)、gas 有界(產生大整數付比例 gas)→ LOW–MEDIUM 健全性/DoS,非 critical**。bare-literal `**`/`<<` 已由 COW-2293 deploy 靜態堵住;airtight 需 **VM 層(Rust)強制**(int_overflow.rs 註解已標「另案追蹤」)。→ **[node#1007](https://github.com/cowboyinc/node/issues/1007)**(附三個實測 repro)。**已完整閉合 → draft PR [node#1009](https://github.com/cowboyinc/node/pull/1009)(Closes #1007)**:**VM 層(Rust)強制**——`Settings.max_int_bits`(從 DeterminismOptions 設)+ `int::ensure_int_bits` 掛在所有成長運算(`+`/`-`/`*`/`**`/`<<`)與中央 `with_value` 構造 + math factorial/comb/perm。實測 `pow(2,N)`/`2**N`/`1<<N`/`math.factorial`/`capped*capped`/`int(str)`/`from_bytes` 全堵、sub-cap 放行;pvm serial 282/0(並行 cow2433/2434 是既有 warm-pool flaky,devnet baseline 同樣)。**supersede** 只做 construction 半的 [#1008](https://github.com/cowboyinc/node/pull/1008)(Python preamble `__new__`)。皆 flag-day。中間過程:先 #1008(preamble 半)→ 用戶要求做 VM 層 → #1009 完整。

---

## 2. 確認發現 — HIGH(完整詳情)

### H-1. [cip-13-runner-delegation.md] `MIN_SELF_BOND_BPS`(10%)定義了卻在委託受理 handler 中從不強制
- **維度:** security ｜ **位置:** §3.2 Effective stake — Minimum self-bond 段落
- **描述:** §3.2 寫「runners MUST maintain self_stake >= max(MIN_STAKE_CBY_WEI, effective_stake × MIN_SELF_BOND_BPS / 10000)」。這 10% skin-in-the-game 約束是防止「零自有資本的 runner 指揮委託資金」的主要經濟安全屬性。常量 `MIN_SELF_BOND_BPS = 1_000` 已定義並存在 genesis 治理參數,但 `handle_runner_delegate_stake`、`handle_runner_increase_delegation`、`handle_runner_update_delegation_config` 全都沒有對它做檢查。當 `max_delegated_stake = 0` 時,自有質押僅 10,000 CBY 的 runner 可接受**無上限**委託,遠超該約束隱含的 9:1 上限,實際自有 bond 比例趨近於零、無有意義的可罰自有質押。
- **證據:** 規格 §3.2 上引;代碼 node/runner/src/types.rs:298 定義 `MIN_SELF_BOND_BPS: u16 = 1_000`;`grep -rn MIN_SELF_BOND_BPS node/execution/` **零命中**——該常量在任何 handler 中都沒被讀;委託前置檢查 node/execution/src/runner/delegation.rs:338-419 檢查了 amount floor、delegator cap、tranche cap、runner cap,但沒查 self-bond 比例。
- **建議:** 在 `handle_runner_delegate_stake` 與 `handle_runner_increase_delegation` 加前置條件:算出 `proposed_total_active = totals.total_active + amount` 後,驗證 `runner.stake >= max(MIN_STAKE_CBY_WEI, (runner.stake + proposed_total_active) × min_self_bond_bps / 10000)`;`handle_runner_update_delegation_config` 設定 `max_delegated_stake` 時亦須滿足自有 bond 比例。或明確在規格改為「advisory(非協議強制)」——但 §3.2 的 MUST 不允許這種讀法。

### H-2. [cip-15-public-asset-hosting.md] Schema 與儲存位置漂移:上鏈代碼實作的是另一份規格(CIP-15 v2)
- **維度:** drift ｜ **位置:** §6.1–§6.2(routes 表存於 `__cowboy/routes`)、§6.6(route 解析)、§6.2 schema(verb/target/pays/enabled)
- **描述:** 被審規格描述 routes 存於 actor KV 保留鍵 `__cowboy/routes`,為統一的 `Routes { routes: list<Route> }`,每個 Route 帶 `verb`、`path`、`target`(Method|Volume|Runner)、`pays`、`price`、`priority`、`enabled`。上鏈代碼 node/ras/src/route_manifest.rs 實作的是「CIP-15 v2」,schema 根本不同:(a) 存於 STORAGE_MANAGER(0x0A),經 `UpdateRouteManifest` 系統指令(opcode 102)寫入,而非 actor KV;(b) schema 拆成 `static_routes` 與 `dynamic_routes`——無 verb 欄、無 target 多型、無 Runner 型、無 pays/price/enabled;(c) 新增規格沒有的 `default_behavior: u8`(0=DYNAMIC,1=STATIC);(d) 強制 `ROUTE_PRIORITY_GAP = 1` 不變量(`min(dynamic.priority) >= max(static.priority) + 1`,錯誤碼 `ERR_ROUTE_PRIORITY_INVERSION`)——規格完全沒有;(e) 上限拆成 MAX_STATIC_ROUTES=100 + MAX_DYNAMIC_ROUTES=100,而非規格的統一 MAX_ROUTES=200。忠於被審規格的實作與部署鏈不相容。
- **證據:** 規格 §6.1/§6.2 上引;代碼 route_manifest.rs:1「CIP-15 v2 Part II §4」、:25-28 兩個 MAX_*_ROUTES=100、:32 `ROUTE_PRIORITY_GAP: u16 = 1`、:56-60 `DynamicRoute { path_prefix, priority }`(無 verb/pays/enabled);node/execution/src/ras.rs:30 `STORAGE_MANAGER_SYSTEM_ACTOR_ID: u64 = 0x0A`;node/types/src/execution.rs:6603 `assert_eq!(SYS_UPDATE_ROUTE_MANIFEST, 102)`。
- **建議:** 對齊規格與上鏈實作:更新規格反映 v2 schema(static/dynamic 分表、僅 path-prefix、存 STORAGE_MANAGER、opcode 102),或明列哪些延後。至少加一則規範性 errata 標明 v2 分歧點與 opcode 編號。

### H-3. [cip-20-fungible-tokens.md] 三個上鏈指令規格完全缺失:TokenIncreaseAllowance / TokenDecreaseAllowance / TokenPermit
- **維度:** completeness ｜ **位置:** §Host Functions / Approvals(約 318–341 行);§Security Considerations / Approval Race Condition(約 572 行)
- **描述:** 規格把 increase_allowance/decrease_allowance 當成範圍外的 SDK 輔助(「本 CIP 不規範但建議 SDK 提供」)。實際上三者都是完整規範的上鏈系統指令,並已分配 opcode:SYS_TOKEN_INCREASE_ALLOWANCE=21、SYS_TOKEN_DECREASE_ALLOWANCE=22、SYS_TOKEN_PERMIT=23。TokenPermit 實作 EIP-2612 等價的 gasless 授權(deadline、nonce、secp256k1 簽名),有自己的錯誤碼 1413-1415 與重要安全屬性(防重放、chain_id 綁定 per COW-1074)。全都沒被記錄,client 無規格可依。
- **證據:** cowboy-protocol/crates/cowboy-protocol-codec/src/instruction.rs:46-49 定義 21/22/23;handler node/execution/src/token/core.rs:567-638(handle_token_permit);派發於 node/execution/src/execution/system_instruction.rs:427-463。
- **建議:** 把三個操作規範為一等 host function,含 wire 格式(Permit:owner、spender、value、deadline、nonce、signature)、auth 規則、錯誤碼、permit digest 的 domain-tag 構造。

### H-4. [cip-25-cross-chain-architecture.md] §2.2 排序保證與 §B.2 的 L2-Ordering 不變量互相矛盾
- **維度:** consistency ｜ **位置:** §2.2(Delivery Semantics)vs §B.2(L2-Ordering)與 §2.3(deliver() 偽碼)
- **描述:** §2.2 稱「per-(sender, dst_chain) 排序……由要求連續 nonce 來強制」;§B.2 直接相反:「協議允許亂序投遞,應用若要 per-sender 單調排序,MAY 由收方自行強制」;§2.3 deliver() 僅檢查 `!consumed[msg.src_chain][msg.sender][msg.nonce]`,無連續性要求。沒有任何東西阻止 nonce 5 在 nonce 4 之前被投遞。§2.2「由要求連續 nonce 來強制」為假:nonce 在源端連續分配,但投遞層不強制投遞順序。
- **證據:** §2.2、§B.2、§2.3 上引(deliver() 只有 consumed 檢查,無 contiguity 檢查)。
- **建議:** 對齊 §2.2 與 §B.2。正確說法:源端 mailbox 分配單調遞增 nonce,但 L2 投遞層**不**強制投遞順序,只保證 exactly-once 消費。刪去 §2.2「由要求連續 nonce 來強制」一句,或改為「源端 nonce 連續分配,供應用在收方層自行強制排序」。§B.2 措辭較精確,應作為規範定義。

### H-5. [cip-26-account-libraries.md] §3.6 gas 常量與上鏈代碼大幅分歧
- **維度:** drift ｜ **位置:** §3.6 gas 表
- **描述:** §3.6 表中每個 gas 數值都與實作不符。PublishLibrary base cycles:規格 100,000,代碼收 200(LIB_INSTRUCTION_BASE_CYCLES);per-byte cycles:規格 50,代碼 100;per-byte cells:規格「新 blob 才 len(code) cells,否則 0」(依 blob 是否存在條件計),代碼**無條件**收 len(code)×200 cells(即使快取命中);per-pin overhead:規格 1,000 cycles,代碼 300(STORAGE_READ+WRITE=100+200);per-handler-call lib load:規格 len(code)×5 cycles,代碼熱路徑 1 cycle/byte、冷路徑 53 cycle/byte。照規格實作的獨立節點會把 publish base 費算高 500×、per-byte 費算成一半,導致共識分歧。
- **證據:** 規格 §3.6「100_000 + len(code)*50」cycles、新 blob 才 len(code) cells;代碼 node/execution/src/gas.rs:442/447/451/456/465/468 對應 200/100/200/300/1/53;cell 無條件收費見 library_instruction.rs:72-74 無 blob 存在守衛。
- **建議:** 更新 §3.6 為實際常量,補上 cached(1 cyc/byte)vs cold(53 cyc/byte)handler load 區分,並註明 cell 收費是無條件(非依 blob 新舊)。

### H-6. [cip-3-fee-model.md] §2.2.3 lane budget 表相對上鏈代碼嚴重錯誤,且不在 amendment 範圍
- **維度:** drift ｜ **位置:** §2.2.3 Execution Lanes 表
- **描述:** §2.2.3 表:System=500,000(5%)、User=5,000,000(50%)、Runner=2,500,000(25%)、Timer=2,000,000(20%),合計 10,000,000。上鏈常量:LANE_USER_CYCLES=22,222,222、LANE_RUNNER_CYCLES=8,888,888、LANE_TIMER_CYCLES=8,888,890、LANE_SYSTEM_CYCLES=40,000,000(合計 80M)。代碼中 System 佔區塊 50%,而非 5%。amendment 的 Warning box 明確更新了 T_c、T_b、alpha、DENOM、MIN/MAX_BASEFEE、transfer cost,唯獨隻字未提 lane budget。任何只讀規格本文或 amendment 的替代 client,會用比參考實作小達 80× 的值劃分區塊空間,立即共識失敗。
- **證據:** §2.2.3 表「System | 500,000 | 5%」;代碼 node/types/src/constants.rs:102 LANE_SYSTEM_CYCLES=40_000_000、:82 BLOCK_CYCLES_TARGET=20_000_000;測試 spec_mg_1_lane_budgets_sum_correctly(basefee.rs:897)斷言 `LANE_SYSTEM_CYCLES == 2 * BLOCK_CYCLES_TARGET` 且合計 = 4×target = 80M。
- **建議:** 更新 §2.2.3 表為現值:User=22,222,222(~27.8%)、Runner=8,888,888(~11.1%)、Timer=8,888,890(~11.1%)、System=40,000,000(~50%),合計 80,000,000;說明 System lane 為 2× BLOCK_CYCLES_TARGET。把這條加入 amendment Warning box。

### H-7. [cip-3-fee-model.md] 4096-bit 整數守衛在 VM 字節碼層可繞過;§2.2.4.9 的 MUST 僅部分強制
- **維度:** security ｜ **位置:** §2.2.4.9 Large Integer Precision Limit
- **描述:** §2.2.4.9 稱「整數位長 MUST NOT 超過 4096 bits;任何超限運算會拋 OverflowError」。實作在部署期經 validate_actor_code 注入 INT_GUARD_PREAMBLE 的 _GuardedInt。工作區 CLAUDE.md 明載:「裸字面量 2**10000 會繞過此守衛(VM 字節碼路徑);完整 VM 級強制已延後」。未經 patched builtins.int 派發的動態指數等 bigint 運算,執行期仍可產生任意精度結果,違反 MUST,留下活的 DoS 面(動態 `pow(2, 100000000)` 可耗盡記憶體/CPU)。
- **證據:** §2.2.4.9 上引;CLAUDE.md 上引;node/execution/src/pvm_executor.rs:182 的 MAX_INT_BITS=4096 檢查僅在部署/驗證期,不在逐字節碼執行熱路徑。
- **建議:** 在 VM 級強制完成前,把 §2.2.4.9 的 MUST 降為 SHOULD,並明註目前僅部署期靜態分析;開一條規範性 follow-up(比照 COW-970)釘住動態執行期強制生效的區塊高度;代碼加 VM 級 hook 攔截整數運算,結果超 4096 bits 即拋 OverflowError。

### H-8. [cip-30-per-actor-storage-root.md] CIP-27 的 sealed-storage 排除與 CIP-30 的 O(1) root-copy fork 不可調和
- **維度:** consistency ｜ **位置:** §3.4(CIP-30)vs CIP-27 §3.3
- **描述:** CIP-27 §3.3 規範性要求 fork() 時「CIP-24 sealed 儲存項 MUST 排除於儲存複製之外」,並稱「這不是揮手帶過——子代無法帶內重新封裝父代 sealed 的 DEK,是 CIP-24 的硬限制」。CIP-30 §3.4 卻要求 fork() 無條件 `child.storage_root = parent.storage_root`——複製 root hash 即繼承整棵父樹(含 sealed 項)。要排除 sealed 項只能重建過濾樹,是 O(sealed 數),非 O(1)。兩條規範性 MUST 不可並存:要麼「有 sealed 儲存的 actor O(1)」為假,要麼違反 CIP-24 排除安全要求。CIP-30 完全沒提 CIP-24 sealed 儲存。
- **證據:** CIP-30 §3.4「子代儲存 IS 父代的」;CIP-27 §3.3 表「CIP-24 sealed 儲存項 MUST 排除」、§7「無法帶內重封裝是 CIP-24 硬限制」。
- **建議:** CIP-30 §3.4 必須明確處理 CIP-24 排除。三選一:(a) 定義「過濾 fork 樹」重建子代儲存(接受 O(sealed)成本並記錄失去 O(1));(b) 要求 on_fork 在 root-copy 後立即刪除子代 sealed 項;(c) 與 CIP-27 協調,改依 CIP-24 協議內存取控制拒絕子代讀父代 sealed DEK。所選方案須在兩份 CIP 都規範化。

### H-9. [cip-31-cbfs-rent-schedule.md] CIP-31 的費用拆分 10/1/89 與 CIP-9、白皮書、代碼、架構文件(10/2/88)矛盾
- **維度:** consistency ｜ **位置:** §Abstract、§4 Fee Distribution Split、§8 Slashing Schedule、Security §4
- **描述:** CIP-31 定義 STORAGE_FEE_CHALLENGE_POOL_BPS = 100(1%)、STORAGE_FEE_RELAY_BPS = 8900(89%),通篇以「10/1/89」呈現。其餘所有權威來源——CIP-9 §5.6/§10.4、儲存白皮書(POR_CHALLENGE_FEE_SHARE = 2%)、架構文件——皆為 10/2/88。上鏈代碼 node/ras/src/lib.rs:50-51 為 200 與 8_800。測試檔 node/ras/tests/cip31_split_test.rs:17 標題即「§4: three-way 10/2/88 split」。唯 CIP-31 一份聲稱 1%/89%。
- **證據:** CIP-31 §4「= 100(1%)」「= 8900(89%)」;node/ras/src/lib.rs:50「= 200; // 2%」、:51「= 8_800; // 88%」;CIP-9 §5.6「= 200」。
- **建議:** 更正 CIP-31 §4 為 200(2%)與 8800(88%),更新全部散文(Abstract、§4 表、§8、Security §4)與 §6 MIN_RELAY_STAKE 營收估算(現用 89%)。

### H-10. [cip-31-cbfs-rent-schedule.md] 儲存費計價不符:規格 per-MiB(450 nano-CBY)vs 代碼 per-byte(10 nano-CBY)——~23,301× 費率差
- **維度:** drift ｜ **位置:** §1 Storage Fee Rate
- **描述:** CIP-31 §1 定義 STORAGE_FEE_PER_MIB_PER_EPOCH = 450 nano-CBY,並自陳「最小整數 per-byte 費率(1 nano-CBY/byte/epoch)≈ $392/GiB/年,高於商品物件儲存三個數量級,故 per-byte 粒度無法表達有競爭力費率」。但代碼 node/ras/src/lib.rs:43 定義 STORAGE_FEE_PER_BYTE_PER_EPOCH = 10(per byte)。換算 per-MiB:10 × 1,048,576 = 10,485,760 nano-CBY/MiB vs 規格 450——約 23,301×。按代碼費率,儲存約 $3,920/GiB/年,而非規格目標 ~$0.17/GiB/年。
- **證據:** CIP-31 §1 上引;node/ras/src/lib.rs:42-43「STORAGE_FEE_PER_BYTE_PER_EPOCH: u128 = 10;」。
- **建議:** 對齊計價。(a) 代碼改以 nano-CBY/MiB 儲存費率、billing 時換算,取與 450 一致的值;或 (b) 規格改用更小單位(如 pico-CBY/byte)使有競爭力整數費率可表達。規格自己反對 per-byte 整數,故 (a) 為正解。

### H-11. [cip-5-timers.md] 超預算 carry-forward timer 其實沒被延到下一區塊
- **維度:** drift ｜ **位置:** §6.5 Lane Budgets — Flow Control, Not Free Gas
- **描述:** §6.5 稱「gas_limit_per_fire 超過剩餘 lane 預算的 timer 延到下一區塊」。代碼的 carry-forward Preserve 路徑只更新 timer 的 skip_count 並把 timer 重存回**原本的高度桶**(timer.height = current_height)。後續區塊呼叫 get_timers_by_height(current_height+N) 是精確高度查詢,無法回傳存在較早 current_height 的 timer。超預算 carry-forward timer 因此對任何未來區塊的 EOB timer 迴圈都不可達,只會留到 TTL 過期被 GC(若 GC 預算足)。「延到下一區塊」的保證不成立。
- **證據:** §6.5 上引;node/storage/src/speculative.rs:1380-1415(Preserve 路徑,height 未變);node/storage/src/timers.rs:174-179(精確高度查詢);speculative.rs:885(僅以 current_height 呼叫);對照 retry 路徑 speculative.rs:1632 用 `height: current_height + 1`。
- **建議:** (a) 修 carry-forward 把 timer 重新分桶到 current_height+1(比照 retry 路徑);或 (b) 更正 §6.5 為 timer 留在原排定高度、僅在該高度可處理(若該高度預算永久耗盡即遺失)。並把 dead-letter 門檻 TIMER_MAX_CARRY_FORWARD=256 寫入規格。

### H-12. [cip-8-mpp-session.md] §12 全錯:session handler 是 opcode 52–57 的 SystemInstruction 變體,不是 ActorMessage
- **維度:** drift ｜ **位置:** §12「Opcode / SystemInstruction question(V-12 closure)」
- **描述:** §12 明稱「MPP Session handler……不是新的 SystemInstruction 變體,而是以 typed selector 派往 SESSION_ACTOR=0x0C 的 ActorMessage」「MPP Session 從未主張數字 opcode」。兩者皆假:代碼分配 SYS_SESSION_OPEN=52 … SYS_SESSION_SLASH=57 作為標準 SystemInstruction 變體,走正常系統指令 handler 派發。§12 描述的「V-12 closure」與現實不符:與 CIP-13 v2(52-56)、CIP-23 v2(57)的衝突是靠那些 CIP 改號至 ≥87 解決,而非 CIP-8 放棄 opcode。
- **證據:** §12 上引;cowboy-protocol-codec/src/instruction.rs:126-136 定義 52–57;node/execution/src/execution/system_instruction.rs:3472,3629,3643,3660,3667,3674 以變體派發;CIP-13 v2 master 表(cip-13 line 816)確認「52-57 = CIP-8 Session ✅ in code」。
- **建議:** 重寫 §12 講事實:session handler 是 opcode 52-57 的 SystemInstruction;V-12 衝突由 CIP-13/CIP-23 改號解決,非派發機制改變;刪去所有 ActorMessage selector 說法;node/types/src/execution.rs 的 sys_opcode_uniqueness 測試須納入 SYS_SESSION_* 常量以補回歸漏洞。

### H-13. [cowboy-design-decisions.md] 通脹曲線與技術白皮書矛盾
- **維度:** consistency ｜ **位置:** Economic Model — Validator Rewards
- **描述:** 設計文件稱驗證人獎勵來自「遞減通脹表(第 1-2 年 5%,降至 1.5% 終值)」。共權威的技術白皮書(§8.2)則:Bootstrap 1–2 年 8%/6%、Glidepath 3–4 年 4%/3%、Steady-state 5 年起 2% 下限。第 1 年(5% vs 8%)、第 2 年(5% vs 6%)、終值(1.5% vs 2%)三者皆不一致。
- **證據:** 設計文件上引;技術 WP §8.2 表(cowboy-technical-whitepaper.md 740–744 行)。
- **建議:** 對齊兩份文件到單一權威通脹表,與經濟團隊確認正確數字,更新設計文件與技術白皮書一致。

### H-14. [cowboy-secrets-whitepaper.md] `MIN_PROXY_STAKE`:規格 10,000 vs 代碼 1,000 token units(10× 差)
- **維度:** security ｜ **位置:** §13 參數表
- **描述:** 規格參數表定 MIN_PROXY_STAKE = 10,000 token units;代碼強制 CBSS_MIN_PROXY_STAKE = 1_000(node/types/src/constants.rs:642)。質押降低削弱對 proxy 失當行為的經濟嚇阻(罰 5% 於 1,000 = 50 vs 於 10,000 = 500),使委員會 Sybil 便宜 10×(與 econ-fees 主題發現一致)。
- **證據:** 規格 §13「MIN_PROXY_STAKE | 10,000 token units」;代碼 node/types/src/constants.rs:642「pub const CBSS_MIN_PROXY_STAKE: u64 = 1_000;」。
- **建議:** 對齊規格與代碼的值與單位基準(token units vs wei),確認正確的經濟門檻並二者統一;此值影響 CBSS 委員會抗 Sybil,須人工核定後 flag-day。

### H-15. [cowboy-storage-whitepaper.md] DEK 封裝機制:WP 寫 HKDF,上鏈代碼用 CBSS 門限-IBE 委員會
- **維度:** drift ｜ **位置:** §3.1 DEK generation;§4.1 Volume Lifecycle — Create;§10.8 Dispatcher trust
- **描述:** WP 指定以未定義的 `account_secret` 做 HKDF-SHA256 作為 DEK 封裝——純本地、單方金鑰派生。上鏈實作用 CBSS(CIP-24)門限委員會金鑰材料封裝 DEK:`CreateVolumeInstruction` 帶 `cbss_committee_epoch` 與 `cbss_release_key_material_hash`,建立 volume 時對存於 `CBSS_SYSTEM_ACTOR (0x04)` 的 `cbss::AccountReleaseKey` 驗證。信任模型根本不同:HKDF-local 只需擁有者持有 secret;CBSS 需門限委員會 quorum 才釋放 DEK。WP §10.8 說「v2 才走 Secrets Manager(0x04) 封裝」,但那在代碼已是 v1 現實。
- **證據:** WP §3.1「HKDF-SHA256(account_secret, ...)」;代碼 node/execution/src/ras.rs:218-242 從 CBSS_SYSTEM_ACTOR 載入 `cbss::AccountReleaseKey`;ras.rs:2234「private volume requires wrapped_dek and a non-zero cbss_committee_epoch」。
- **建議:** 更新 §3.1/§4.1 以 CBSS 門限-IBE 委員會封裝為規範性 DEK 保護機制,記錄 committee epoch 綁定、`cbss_release_key_material_hash` 欄與 CBSS 釋放條件;刪去 HKDF/account_secret 說法。

---

## 3. 確認發現 — MEDIUM(170 條,依文件分組)

**changelog** (1)
- [drift] WP §9.1 把 INTENT_SETTLEMENT(0x14)列為「spec-allocated」,但代碼已有 active handler

**cip-1-actor-scheduler** (3)
- [drift] LANE_TIMER_CYCLES 陳舊:規格 2,000,000,代碼 8,888,890
- [drift] 預設 GBA p50 priority-tip 在上鏈代碼未追蹤/未接線
- [drift] 公平權重 W(actor) 用的是競爭集中位數,非全網視窗中位數

**cip-2-offchain-compute** (4)
- [drift] 規格的 CrashAttestation struct 與上鏈的 SubmitCrashAttestation 指令不符
- [drift] EntitlementGrant wire 格式顯示 Vec<u8> blob,代碼用 typed Scope/Action/Constraints 欄
- [comp] aggregator_timeout_blocks 被引用但規格從未定義
- [comp] CIP-2 參數的治理 opcode 94-100 在 CIP-2 中沒提

**cip-3-fee-model** (3)
- [drift] §2.4 EIP-1559 公式參數(alpha、clamp、T_c、T_b、cell 容量)在本文錯誤;amendment Warning 未劃掉衝突文字
- [drift] Storage KV Read 在 §2.2.1 表定 10 cycles,上鏈 100 cycles(Model C 重定價);amendment 未註記
- [cons] §2.4 區塊 cell 容量(1,000,000)與 amendment 隱含容量(8,000,000)衝突;amendment 只給 target 未給 capacity

**cip-4-storage** (9)
- [drift] Key prefix 表自 0x00 起即錯——每個 light-client 查詢都壞
- [drift] Actor code 規格為 per-address 儲存,代碼為 content-addressed 於 0x0F
- [drift] Timer index key 代碼用 keccak(height),規格稱 raw height bytes
- [drift] Receipt root 用 commonware-codec 編碼,規格稱 RLP
- [drift] Rent 費率預設代碼比規格高 1000×
- [drift] Rent 參數存於單一合併 key,規格列五個獨立治理 key
- [drift] SNAPSHOT_INTERVAL 規格(1024)不符代碼(100,000)
- [comp] 16 個上鏈 state prefix(0x0E–0x1D)規格完全缺
- [drift] Mailbox 儲存模型:規格 per-actor VecDeque,代碼用 indexed 個別訊息

**cip-5-timers** (1)
- [drift] §3.1 Timer struct 缺 4 個上鏈欄;§4.1 schedule_timer_ex API 缺 2 參數

**cip-6-sdk** (1)
- [drift] 幽靈 entitlement:`bank.transfer` 不存在——代碼查 `econ.transfer`

**cip-7-simple-stream-protocol** (1)
- [comp] SUBSCRIBER_PAID 攝取路徑架構上不可實作,且 SDK 呼叫簽名壞掉

**cip-8-mpp-session** (1)
- [drift] Finalize 過期 Open session 路徑有規格無實作

**cip-9-runner-storage** (2)
- [drift] RelayNodeProfile 欄與型別與規格分歧
- [drift] 規格的 relay 健康衰減模型未實作——改為 status flag

**cip-10-runner-containers** (5)
- [cons] CIP-13 v2 master opcode 表仍列 CIP-10 舊的 61–64,與 CIP-10 v2 的 160–164 矛盾
- [secu] 非 TEE 計費爭議時把 full max_compute_cost 給 runner,製造誇報誘因
- [secu] 誤把 CAP_NET_BIND_SERVICE 認定為對外網路存取所需
- [cons] §11.3 key 格式產生 66-byte key 且用錯 CIP-4 prefix,違反 54-byte 固定 key 契約
- [comp] setup 期間呼叫 skip_task() 時計費 escrow 的歸屬未定義

**cip-11-runner-connectivity** (1)
- [drift] mru_key/MruRecord 狀態與 PresenceInput block 欄為規範必需,但代碼完全缺

**cip-12-governance** (10)
- [drift] CircuitBreaker 與 UpgradeSystemActor 寫死 0x01–0x0D,排除已部署 actor 0x0E–0x10 與 0x1E
- [drift] §4.2「canonical example」:BasefeeConfig 在 0x06,非 0x09.params
- [drift] 擴充範圍 0x0E–0x13 稱「尚未在代碼」給 CIP-14/10/18/28——其中三個已作為 CIP-16 actor 部署
- [secu] §7.4.b migration 以「unlimited gas」執行——無窮迴圈 migration 會永久停產區塊
- [comp] 眾多失敗模式卻無定義任何錯誤碼
- [drift] Pause/rollback 時間常量是 demo 級區塊數,非真實時長
- [secu] CircuitBreaker 7-of-9 Council 認證延後到未指定的外部層
- [drift] Proposal ID:規格 bytes32 vs 代碼 u64 單調計數
- [drift] UpgradeSystemActor payload 缺 §7.1 的 code_ref/migration/spec_ref 欄
- [comp] quorum/參與檢查的「active stake」分母未定義

**cip-13-runner-delegation** (4)
- [drift] JobSettled 與 DelegatorPayout 事件(§3.5 MUST)代碼未 emit——明確延後
- [cons] §7.1 實作註「schedule in unbonding queue」直接與 §3.8 矛盾
- [comp] 代碼強制未記錄的 MAX_TRANCHES_PER_DELEGATOR = 32(Active+Unbonding 合計)
- [comp] epoch_slashed 儲存 key 不在 §3.1 佈局;無限 key 累積未規範

**cip-14-dns-addressable-actors** (1)
- [cons] Part I 的費用拆分加總達 120%

**cip-15-gateway-implementation** (4)
- [cons] Resolver tie-break 偽碼在 Method>Runner>Volume 排序中漏掉 Runner
- [cons] 驗證失敗 cache 行為與規範 CIP-15 §6.8 矛盾;規範本身亦自相矛盾
- [cons] GET_STATE 稱「無任何 CIP 規範」但 CIP-17 存在且規範它
- [comp] Runner-target 派發在建置順序中無實作階段

**cip-15-public-asset-hosting** (3)
- [drift] RoutesUpdateRateLimited 速率限制未實作
- [secu] route_serving_endpoint 的 SSRF 驗證未規範(註:上鏈 gateway 代碼已緩解,見 §6)
- [comp] Caller-Auth 的 domain_tag 值規格缺

**cip-16-custom-domains** (5)
- [drift] NamespaceKind enum 在代碼與規格語義完全不同
- [drift] DomainBinding record schema 缺 5 欄、2 個型別變更 vs 上鏈
- [secu] 「Frozen-ACTIVE」:CIP-5 timer 餘額耗盡且事件訂閱失敗時,過期綁定仍停在 ACTIVE
- [drift] Registry settlement config 儲存 key 名規格與代碼不同
- [drift] Registry entry 數斷言陳舊;ingress.http 已部署

**cip-17-verifiable-state-read** (5)
- [drift] Proof wire 格式規格是 MPT-schema,代碼是 QMDB/MMR——§5.2 client 驗證演算法不可實作
- [drift] `state_root` 語義錯——規格稱 per-actor 儲存 trie root,實作回傳全域 state root
- [drift] 缺鍵排除證明用獨立 `exclusion_proof` 回應欄,非同一 `proof` 物件——回應 schema 與規格分歧
- [cons] CIP-17 引用「CIP-4 / MPT primitives」從未部署——CIP-4 本身已把 MPT 換成 QMDB
- [comp] §5.4 錯誤表漏 Cowboy 應用錯誤碼;§9 rate limit 描述不準確

**cip-18-payments** (3)
- [secu] method=cowboy 授權 struct 缺 chain_id——可跨部署重放
- [comp] deduct_budget 與 credit_inbound 的 caller 授權機制未規範
- [comp] PaymentGate 失敗模式無定義 Cowboy 專屬錯誤碼

**cip-19-gateway-mcp-ingress** (2)
- [cons] MCP endpoint 啟用 entitlement 在 CIP-18 §13.1 與 CIP-19 §7 衝突
- [cons] §9 廣告 `listChanged: true`,但 §4、§8 明確延後 server 主動通知

**cip-20-fungible-tokens** (4)
- [drift] token_transfer_batch 拒絕 hooked token,雖規格稱每 leg 呼叫 hook
- [cons] Hook 約束對「on_transfer gas-cap 失敗是否 revert 轉帳」自相矛盾
- [comp] 協議級 MAX_TOKEN_SUPPLY(1e30 wei)不在規格;與「None=unlimited」矛盾
- [cons] u128 型別更新後,規格本文型別註解仍保留 u256

**cip-21-liquidity-pools** (3)
- [drift] State-Triggered Timer API(`trigger_type='state'`)不存在
- [drift] schedule_timer 的 `interval=`/`handler=` 參數在 PVM API 不存在
- [cons] V3 Hook 介面與「Same as V2」聲稱矛盾

**cip-22-continuous-clearing-auctions** (6)
- [secu] 雙重 finalize:`clear_block` 與 `finalize` timer 同一區塊都呼叫 `_finalize_auction()`
- [secu] 最終 clearing 區塊 `_remaining_demand` 除以零
- [drift] 規格用的 Timer API 在 CIP-5 與上鏈實作都不存在
- [cons] CIP-21 Factory 沒有 `get_or_create_*` 方法;所呼叫介面不存在
- [secu] 零滑點 LP seeding 允許 graduation 時搶跑操縱
- [cons] 「timer 佔區塊容量 20%」事實錯誤

**cip-23-tee-execution** (2)
- [secu] UpdateCollateral 不強制 ROOT_UPDATE_DELAY——治理可即時推 collateral
- [comp] TeeAttested 無 wire 格式 VerificationMode 變體——編碼未記錄

**cip-24-secrets-manager** (9)
- [drift] RotateCommittee 簽名 domain 與規格不同——跨實作不相容
- [drift] PROXY_SOAK_PERIOD 生產節點寫死 100 blocks(規格:216,000)
- [comp] ForcedDeregisterCbssProxy(opcode 84)無 §3.5 規格本體
- [drift] REQUEST_FRESHNESS_BLOCKS 規格值(32)比上鏈(384)小 12×
- [cons] §4.2 時間估算內部不一致(混用 1s/block 與 12s/block)
- [drift] GOVERNANCE_REVIEW_BLOCKS 規格(216,000)比代碼(2,592,000)小 12×
- [comp] RequestReshare(opcode 83)與 ExpireLivenessChallenge(opcode 82)缺 §3.5 規格本體
- [drift] LIVENESS_RESPONSE_BLOCKS 規格(100)不符代碼(64),且 1s/block 時間註解錯
- [drift] MIN_PROXY_STAKE 規格(10,000 CBY × 10⁹ wei)與代碼常量(1,000)衝突

**cip-26-account-libraries** (5)
- [cons] 內部不一致:cells_per_pin 在 §3.4 為 32,§3.6 為 ~64,代碼收 64
- [drift] code_size 欄規格 u64,實作 u32
- [comp] 缺 max-library-code-size 與 max-total-lib-bytes 規範上限
- [comp] RemoveLibrary emit 的 LibraryRemoved 事件未規範
- [comp] 傳遞性 library import:§8 宣稱的解析對等,§3.4 機制無法達成

**cip-27-actor-fork** (6)
- [drift] on_fork 錯誤行為與規範 MUST 矛盾——規格說 fork 成功,代碼中止
- [drift] Entitlement 名 bank.transfer 不存在——代碼強制 econ.transfer
- [drift] §5「已知正確性缺口」(endowment write-set)陳舊——代碼已用 staged 路徑
- [drift] HostError::InsufficientFunds 不存在——代碼回 HostError::InsufficientCbyBalance(107)
- [cons] 誤把 CIP-31 認作 actor 儲存 rent——實際 CIP-31 是 CBFS Rent Schedule
- [comp] on_fork fault-success 語義不足——回傳值與 parent signal 未定義

**cip-28-cowboy-agent-banking** (3)
- [secu] tx.fee_payer_override wire 變更的 flag-day 未被承認
- [comp] CloseCard 對任意 CIP-20 token 的餘額清掃規格不足
- [secu] locked_after_transfer 可經共謀第三方雙轉繞過

**cip-29-on-chain-event-hooks** (5)
- [drift] StatePrefix 0x14/0x15 已被 CIP-26 佔用;上鏈用 0x18/0x19
- [drift] unsubscribe/force-unsubscribe 的 gas 餘與 cell 退款只做帳、未上鏈入帳
- [drift] §2.2 EventSub key 格式不符 54-byte StateKey 佈局
- [cons] 「現有 prefix 分配到 0x13」事實錯誤
- [comp] 多個 §6.3「Open Decisions」其實已在上鏈實作

**cip-31-cbfs-rent-schedule** (4)
- [drift] Transfer 費計價不符:規格 per-MiB(10,000 nano-CBY)vs 代碼 per-byte(1)——~105× 差
- [drift] 參數儲存 actor 與 key namespace 不同:規格 0x0B 於 system:cbfs:*,代碼存 0x09(治理)於 cip31.cbfs.*
- [secu] Challenge pool 下溢未定義:pool 餘 < CHALLENGER_BOUNTY(5 CBY)時規格未規範行為
- [comp] POR_RESPONSE_WINDOW 未釘住,雖聲稱補齊每個 CIP-9 TBD;底層 CIP-9 與 WP 值衝突

**cip-33-actor-hiring-and-distribution** (5)
- [comp] 無 Trading Post 方法把 prepaid 餘額移入 PerCall session 保留
- [comp] declaration_id 的 hash 函數 H() 未規範
- [secu] IBE label 編碼格式未規範
- [comp] VolumePath 型別用於三個 state 欄但從未定義
- [comp] one-active-grant-per-(store, declaration) 唯一性不變量未記錄

**cip-34-cross-chain-settlement-near-intents** (4)
- [secu] key 已釋放但所有有效 filling bid 皆守恆失敗時,RevealAuction 可永久卡死
- [cons] §Solver Model 說「v1 不罰」,代碼在 reveal 實作 best-effort slash
- [drift] open_auction 檢查 #4 漏 MIN_TLOCK_LEAD_BLOCKS 約束且回錯 error code
- [drift] MAX_INTENT_DEADLINE_HORIZON = 1,000,000 在 broadcast_intent 強制,但 Parameters 表缺
- [secu] Intent 簽名 digest 對 chain_id 來源規範不足——留 tx.chain_id 歧義

**跨主題(cross-doc / consensus / crypto / econ / opcode-addr)** (28)
- [drift] CIP-1 稱 LANE_TIMER_CYCLES 可經 TimerConfig 治理調參,但 TimerConfig(CIP-5 §6.4)無 lane 欄,代碼視為硬常量
- [drift] design-decisions:VRF 區塊內交易排序未實作;上鏈是 fee-per-byte 排序
- [comp] design-decisions:Progressive Deposit / Same-Block Exponential Pricing 列為 DoS 防禦但未實作
- [drift] secrets-WP:Gas Cycle 成本整表比代碼差 ~15–70×
- [drift] secrets-WP:MAX_SECRETS_PER_ACCOUNT 與 MAX_VERSIONS_PER_SECRET 代碼都更小
- [drift] secrets-WP:LIVENESS_UNANSWERED_DECREMENT_BPS 規格 250 vs 代碼 100
- [secu] secrets-WP:HEALTH_RECOVERY_BPS_PER_BLOCK 未實作
- [cons] secrets-WP:Slash 健康懲罰規格固定 2,500 BPS,代碼用 per-class BPS
- [drift] storage-WP:Owner CapToken TTL 常量與上鏈差 3×/6×
- [cons] storage-WP:全文區塊時間假設內部不一致
- [cons] storage-WP:§5/§8.2 稱 relay 拿 90%,代碼給 88%(2% 轉 PoR challenge pool)
- [cons] storage-WP:STORAGE_GRACE_EPOCHS 名為 epoch、定義用 block、代碼單位 epoch——三重單位不符
- [drift] storage-WP:Erasure 參數界 WP 2≤K≤16,1≤M≤8;代碼允許 K=1 且 K+M 達 32
- [cons] storage-WP:§4.1 Create 說鏈「生成」DEK,§3.1/§10.1 卻暗示 client 端生成
- [cons] technical-WP:Challenge window「15 分」與「75 blocks」在 1s/block 下矛盾
- [cons] technical-WP:§13 專用 lane 容量百分比與 §6.3/§17.9/代碼矛盾
- [drift] technical-WP:max_tx_size WP §12.1 說 128 KiB;代碼強制 1 MiB(8×)
- [drift] technical-WP:emit_event gas WP 稱 500 cyc + 5 cyc/byte + 0.5 cells/byte;代碼兩者都不收
- [drift] technical-WP:Mailbox 容量 WP 說 1,000,000 bytes;代碼強制 1,000 則(數量上限)
- [comp] technical-WP:PVM 4096-bit 整數約束代碼有,WP §3.1 缺
- [cons] cross-chain:CIP-25 對「L2 是否強制 per-sender 訊息排序」自相矛盾(協議強制連續 vs app-optional)
- [drift] cross-chain:CIP-24 §9.6 標 SEALED-path DKG bootstrap(opcode 158 enactment)未建且阻塞,但 enactment bridge 已上鏈且 CIP-34 宣告 SEALED 已 merged
- [cons] crypto-secrets:RESHARE_INTERVAL_BLOCKS 三方衝突,散文時長全錯(CIP-24「6 月」vs WP「30 天」vs 代碼 ~15 天)
- [cons] crypto-secrets:Proxy soak/unbond 週期在 CIP-24、秘密 WP、代碼間分歧(值與常量名)
- [drift] crypto-secrets:MIN_PROXY_STAKE 兩份規格皆 10,000,代碼強制 1,000,且單位基準不同(wei vs token units)
- [drift] econ-fees:CIP-3 §2.2.3 lane cycle 表(合計 10M)相對 WP §6.3 與代碼(合計 80M)陳舊;LANE_TIMER_CYCLES 2M vs 8,888,890
- [drift] econ-fees:CIP-20 token_create cell 成本規格 len(name)+len(symbol)+256 vs 代碼固定 5,000 cells
- [drift] opcode-addr:上鏈 runner-delegation opcode 119-123(CIP-13)不在任何 CIP opcode 表;CIP-13 Part I §3.3 仍列已退休的 40-44 佔位

---

## 4. 確認發現 — LOW / INFO(127 條)

| 文件 | 維度 | 嚴重度 | 標題(中譯) |
|-----|-----|-----|-------|
| changelog | comp | LOW | 4 月 changelog 加入的 §3.6「Atomic Actor Initialization」在現行 WP 缺失 |
| changelog | drift | LOW | changelog 稱「next free slot(0x14 next)」但 0x14 已分配,無轉換記錄 |
| changelog | drift | LOW | 6/13 changelog 稱 WP 涵蓋「0x01–0x13 + virtual 0x1D」,但現行 WP 另有 0x1E TradingPost(已上鏈)無 changelog |
| C1 | drift | LOW | 自訂 bid fee 參數未暴露於 Python actor 綁定 |
| C1 | drift | LOW | 三層物理結構(ring buffer / epoch queue / overflow BST)未實作 |
| C10 | cons | LOW | Part I §11.2 說 resource class 需治理提案;Part II §5 給 system_deployers auth——直接矛盾 |
| C10 | comp | LOW | Capability 預過濾改變 VRF 選取池——共識關鍵改動卻無 flag-day |
| C10 | cons | LOW | v2 §1 地址表默默漏掉 0x0C(SESSION_ACTOR),造成連續密集序列假象 |
| C10 | comp | LOW | 對外 allowlist 的 TLS SNI 驗證未規範,且被 ECH/ESNI 繞過 |
| C10 | cons | LOW | GPU 計費用整秒(gpu_seconds),但 Part II §6 對 CPU/記憶體引入毫秒精度 |
| C11 | comp | LOW | SubmitPresenceCertificate 系統指令未分配 opcode |
| C11 | comp | LOW | ConsumedSeedsV1 固定 48-byte 簽名欄與未來 MinPk 方案切換不相容 |
| C11 | cons | LOW | LIVENESS_TIMEOUT_BLOCKS 被誤述為測試 fixture;實為生產 per-job 逾時預設 |
| C11 | comp | LOW | PRESENCE_RECEIPT_ED25519_VERIFY_CYCLES 值偏軟且權威來源未指定 |
| C11 | comp | LOW | CIP-11 協議 flag 缺 CIP-12 治理層綁定,阻礙正式啟用 |
| C12 | comp | LOW | 大訊息佇列 actor 的 migration quiesce 明確未解(Open Q#7) |
| C12 | cons | LOW | 「Foundation 不能提案」是社會約束,非協議強制 |
| C13 | drift | LOW | VRF 權重公式規格(log2)不符代碼(linear-stake × sqrt-reputation) |
| C13 | drift | LOW | 代碼事件 topic 名與規格名分歧——共識關鍵不符 |
| C13 | comp | LOW | MIN_SELF_BOND 強制位置規格不足——§3.3 前置條件漏此檢查 |
| C14 | secu | LOW | Gateway 失當 slashing 被引用但完全未規範 |
| C15-gw | drift | LOW | MIN_ROUTES_UPDATE_INTERVAL_BLOCKS 強制(RoutesUpdateRateLimited)node 未實作 |
| C15-asset | cons | LOW | §12.5 交叉引用錯(寫 §6.5 應為 §6.8) |
| C16 | drift | LOW | AMEND 2-A/2-B(DnsTxtRecordMatch/DnsCnameMatch)已上鏈,卻被當未來前置 |
| C16 | cons | LOW | Part I §10.2 建議 421,Part II §7.2(canonical)覆寫為 503——文件內矛盾 |
| C16 | comp | LOW | 狀態機有未記錄轉換:Active→Expired、Suspended→Expired、Expired→Active |
| C16 | comp | LOW | EXTERNAL_REVERIFY_FEE 完全未規範——無最小值/預設/治理下限 |
| C17 | drift | LOW | `at_block` 歷史讀被列 Future Work 但已上鏈 |
| C17 | drift | LOW | 陳舊行號引用誤導實作者 |
| C17 | comp | LOW | get_state 的系統 actor 404 豁免規格未記錄 |
| C17 | comp | LOW | Runner 暴露被宣告卻完全未規範 |
| C18 | comp | LOW | PaymentIntent 引用的 PaymentBinding struct 從未定義 |
| C18 | comp | LOW | BudgetConfig.auto_refill 語義(trigger/amount/source)未規範 |
| C18 | comp | LOW | PASS_EXPIRY_BLOCKS 常量與 PassConfig.expiry_blocks 欄關係未定義 |
| C18 | cons | LOW | facilitator 治理引用 CIP-12,但 Requires 缺 |
| C19 | cons | LOW | §8/§15 把 `/_cowboy/mcp` 保留歸給 CIP-14 §8.6,該節未列此路徑 |
| C19 | cons | LOW | §14.3 引 CIP-14 §10 做 route registry cache 刷新;該節只有協議常量 |
| C19 | comp | LOW | `verb=ANY` 的 route 在 MCP 派發預設 POST 無理由——可能對安全操作觸發 command path |
| C2 | comp | LOW | crash_attestation_review_threshold 規格有,但不在 UpdateNonRevealConfig/NonRevealConfig struct |
| C2 | drift | LOW | 治理 config 儲存 key 格式不一:規格暗示 sub-key,代碼用單一 JSON blob |
| C2 | drift | LOW | max_non_reveal_slash_cby(規格名)與 max_non_reveal_slash_wei(代碼欄)單位不符 |
| C2 | drift | INFO | JAIL_EXIT_FLOOR 規格為動態網路中位公式,實作為靜態治理參數 |
| C20 | drift | LOW | 陳舊 Phase-1 警告誤稱 hook gas cap 未強制 |
| C20 | drift | LOW | created_at 存 block_height,非規格所稱 block_timestamp |
| C20 | drift | LOW | token_create cell 成本公式規格與代碼差 ~20× |
| C20 | drift | LOW | 規格中的參考實作路徑不存在 |
| C20 | comp | LOW | Token 建立輸入約束未記錄(name/symbol 長度上限與 UTF-8 要求) |
| C21 | cons | LOW | TWAP 章節標題稱「30 分」但代碼用 5 分週期 |
| C21 | comp | LOW | Sync 事件列於 Events 但參考實作從未 emit |
| C21 | comp | LOW | 任何失敗路徑都無定義錯誤碼 |
| C22 | comp | LOW | 缺必要相依:Requires 標頭缺 CIP-1 與 CIP-5 |
| C22 | comp | LOW | `_get_release_amount()` 被呼叫但規格從未定義 |
| C22 | cons | LOW | `BlockCleared` 事件宣告漏 emit 呼叫中的 `currency_raised` 欄 |
| C22 | secu | LOW | `can_claim` hook 可永久擋住提款且無覆寫 |
| C22 | cons | LOW | 範例拍賣時長與 release schedule 時長矛盾 |
| C23 | drift | LOW | verify_cae 的 gas 成本在代碼未區分 light/full 路徑 |
| C23 | cons | LOW | §3.8.7 block-cycle capacity vs target 用語與 CIP-3/basefee.rs 不一致 |
| C23 | comp | LOW | Nonce 不可預測要求(CIP-11 beacon)無法在鏈上驗證 |
| C23 | comp | LOW | OperatorRootRef wire 格式未定義——阻礙獨立實作 |
| C26 | comp | LOW | 缺錯誤碼表;代碼五個 CIP-26 error 變體未規範 |
| C26 | cons | LOW | CIP-3 交叉引用錯:§2.4 是 basefee,非 determinism gate |
| C26 | cons | LOW | Library 名規格稱「Python identifier 規則」,實際強制更嚴的 ASCII-only 子集 |
| C26 | comp | LOW | MAX_TOTAL_LIB_BYTES 上限規格缺 |
| C27 | drift | LOW | CIP-24 sealed 儲存未排除於 storage copy——規範 MUST 未實作 |
| C28 | comp | LOW | CloseCard 時 card_by_owner/card_by_agent 索引壓縮未規範 |
| C28 | drift | INFO | pvm_executor.rs 中 ScheduledTimer.fee_payer_override 行號引用錯 |
| C28 | comp | LOW | 多指令 tx 的 receiver/syscall_kind 驗證是為未實作功能而寫 |
| C29 | drift | LOW | Zombie-reap 路徑漏對 subscriber 的 cell 退款 |
| C29 | comp | LOW | EMIT_SAME_TOPIC_REENTRY 與治理可調常量並列,實為寫死行為 |
| C29 | drift | LOW | §2.5 SUBSCRIPTION_CELL_COST 與代碼命名常量/計算不符 |
| C3 | secu | LOW | §2.2.3 未規範 lane fee 乘數安全界;mult=0 會造成零 basefee DoS |
| C3 | drift | LOW | §2.2.1.1 的 Phase 2b cutover gate 欄(per_instr_metering_active_height)不在上鏈 BasefeeConfig |
| C31 | drift | LOW | STORAGE_GRACE_EPOCHS 在 security 節被誤述為 86,400 blocks,而非 1 epoch |
| C31 | secu | LOW | Security §1 griefing 損益兩平計算方向錯:兩平是 1/6 relay miss,非 1/10 |
| C33 | drift | LOW | Trading Post 系統 actor 地址規格未載明 |
| C33 | cons | LOW | 本文引 CIP-13 但 Depends-on 標頭缺 |
| C33 | comp | LOW | 整份 CIP 無定義錯誤碼 |
| C33 | comp | LOW | Paused hire 的 renew 行為是靜默 no-op,規格未提 |
| C34 | drift | INFO | LANE_SYSTEM_CYCLES 行號引用陳舊(constants.rs:99 vs 實際 102) |
| C34 | comp | LOW | SubmitSealedBid 檢查順序與錯誤碼 1749–1752 規格未列舉 |
| C34 | comp | LOW | Intent 簽名標「EIP-712-style」但用不相容的自訂 preimage 格式 |
| C34 | comp | LOW | opcode 157 空缺未說明——CancelAuction 從規格撤回無 tombstone |
| C4 | drift | LOW | Key 佈局稱「21-byte routing key」但 Ethereum 式地址為 20 bytes |
| C4 | secu | LOW | proof endpoint 無速率限制,儘管 proof 生成昂貴 |
| C5 | drift | LOW | §3.1 codec 稱加欄需 chain wipe,但代碼向後相容 |
| C5 | cons | LOW | 附錄 A 時序圖把 remove_timer 放執行後;§5.1 文字說之前 |
| C5 | drift | LOW | §4.2 _payload 約定 base64,代碼重序列化為 raw JSON |
| C5 | comp | LOW | SYS_CANCEL_TIMER / SYS_EXTEND_TIMER / SYS_UPDATE_TIMER_CONFIG 的 opcode 未指定 |
| C6 | drift | LOW | cowboy_sdk docstring 稱 FSM 為生產模式;pvm_executor 用 Checkpoint |
| C6 | secu | LOW | §12.10 ownership bootstrap「任意 caller 可設 owner」僅在 init 原子時安全;--no-init 留搶跑窗且無協議守衛 |
| C7 | comp | LOW | WatchtowerRegistry 系統 actor 被引用但無地址分配 |
| C7 | comp | LOW | SealRequestExpired 事件缺 SealRequestEmitted 有的 account_key_id 與 generation 欄 |
| C7 | cons | LOW | 文件標題(Watchtower)與檔名(cip-7-simple-stream-protocol.md)不符 |
| C8 | drift | LOW | Disputed 狀態代碼無欄 vs 規格暗示的欄;加欄是未來 wire 格式 fork |
| C8 | comp | LOW | max_amount 型別 u128 但 escrow 記帳靜默截到 u64::MAX |
| C8 | cons | LOW | Settle 前置 cumulative_amount >= spent 規格允許零增;代碼要求嚴格大於 |
| C8 | secu | LOW | COWBOY_SESSION_CHAIN_ID=1 是以太坊主網;跨網 voucher 重放風險被低估 |
| C8 | comp | LOW | OpenSession 前置 expires_at_block > current_block 未列於 §8.1 |
| C8 | cons | LOW | §8.1 說「escrow 入 SESSION_ACTOR storage」但資金進 SESSION_ACTOR 餘額帳 |
| C8 | drift | LOW | §10 比較表引用的 PaymentGate 0x12 未部署 |
| C8 | comp | LOW | 事件 schema 未規範釘住;indexer 依賴未記錄 wire 佈局 |
| C9 | secu | LOW | CapToken nonce 欄實作缺,使防重放宣稱不準確 |
| C9 | cons | LOW | CapToken §7.1 struct 定義與附錄 C wire 格式內部不一致 |
| consensus | cons | LOW | CIP-5 內部不一:per-timer 排程成本 §DoS 稱 1,000,§6.1 稱 200(SET_TIMER_BASE_CYCLES),與 CIP-3/WP 矛盾 |
| design-decisions | drift | LOW | Timer lane 百分比稱 20%,上鏈約 11% |
| design-decisions | comp | LOW | SemanticSimilarity 是上鏈 VerificationMode,卻不在信任模型表 |
| secrets-WP | drift | LOW | LIVENESS_CHALLENGE_MAX_AGE_BLOCKS 規格 86,400 vs 代碼 480 |
| secrets-WP | comp | LOW | §1.8 domain separator 不完整;代碼有四個未記錄的 |
| secrets-WP | comp | LOW | PROXY_UNBOND_BLOCKS 延遲未強制;無 stake-claim 指令規範 |
| secrets-WP | cons | LOW | §13 參數表時間近似值內部不一致 |
| storage-WP | drift | LOW | Owner CapToken clock-skew:WP ±60s;代碼 ±30s |
| storage-WP | cons | LOW | §10.8 與 §Attach 對處理明文 DEK 的實體命名不一致 |
| storage-WP | drift | LOW | Relay handshake 簽名輸入在代碼有未記錄的 domain tag |
| technical-WP | drift | LOW | State rent 費率規格 0.001 CBY/byte/年,代碼 ~1 CBY/byte/年(WP §13.1 已承認) |
| technical-WP | comp | LOW | §12.1 的 per_actor_per_block_cycles=1,000,000 代碼未強制 |
| cross-chain | cons | LOW | CIP-25 L2 nonce scope 三種寫法(per-(src,sender) vs per-(sender,dst));consumed-map key 漏 dst_chain |
| cross-chain | cons | LOW | CIP-34 RECLAIM_GRACE 稱鏡像 CIP-25 §2.6,卻用短 ~14× 的 grace 與不同基準 |
| crypto-secrets | cons | LOW | 覆寫委員會上限衝突:CIP-24 MAX_OVERRIDE_N=15 vs 秘密 WP MAX_COMMITTEE_N=16 |
| crypto-secrets | cons | LOW | Bond 參數在兩份規格間混用相對/絕對定義(DKG_BOND/DKG_TIMEOUT_SLASH/LIVENESS_CHALLENGE_BOND) |
| crypto-secrets | cons | LOW | 秘密 WP §13 的 block→時長註解錯(DKG_FINALIZE_BLOCKS 與 86,400 列) |
| econ-fees | cons | LOW | UpdateSettlementConfig(opcode 40)與 CIP-13 RunnerUpdateDelegationConfig 佔位撞號 |
| opcode-addr | comp | LOW | CIP-10 容器管理 opcode 160-164 與 CONTAINER_REGISTRY 0x11 僅規格有,上鏈 codec 無 |
| opcode-addr | secu | LOW | 地址 0x06 三重綁定:Basefee actor + Token Registry + TimerConfig store——一地址三規格共享 key namespace |
| opcode-addr | drift | LOW | CIP-8 §12 稱「無 opcode」,代碼把 SessionOpen..SessionSlash 上鏈於 52-57 |
| opcode-addr | comp | LOW | CIP-20 fungible-token opcode 10-23 僅代碼定義,CIP 本文從未編號 |
| opcode-addr | drift | LOW | CIP-29 EVENT_SUBSCRIPTION state prefix 漂移(doc 0x14/0x15 → code 0x18/0x19),曾撞 CIP-26;注意 0x14 state-prefix vs 0x14 actor-address namespace 重疊 |
| opcode-addr | comp | LOW | CIP-33 TradingPost 地址 0x1E 代碼釘住,規格留為未指派「well-known address」|

---

## 5. 需人工裁定 — 驗證者分歧(50 條)

_一個驗證者確認、另一個反駁。其中 23 條(backfill)是第一個(健全性)驗證者確認、但第二個(代碼落地)驗證者被 session 限額掐斷的情形,視為「待代碼核對的疑似確認」。含數條 CRITICAL/HIGH 安全項,優先人工看。_

| 文件 | 維度 | 嚴重度 | 標題(中譯) |
|-----|-----|-----|-------|
| C25 | secu | **CRITICAL** | runner 委員會 attestation 簽名**未認證 state_root** |
| storage-WP | comp | **CRITICAL** | account_secret 未定義——DEK 金鑰封裝模型照寫不可實作 |
| C18 | secu | HIGH | BridgeEvidence 只帶單一 facilitator_sig,§21 卻要求多 runner quorum |
| C18 | secu | HIGH | credit_inbound 可能鑄造無擔保 token——「mint or transfer」未規範 |
| C18 | secu | HIGH | Query 路徑結算競態允許雙重服務:一筆付款資助 N 個 actor 回應 |
| C19 | cons | HIGH | MCP challenge 的 x402_compat 與 CIP-18 §13.6 矛盾(wire 格式衝突) |
| C2 | secu | HIGH | EconomicBond 目標驗證未實作,WP 卻定位為信任模型保證 |
| C21 | secu | HIGH | Hook gas cap 宣稱不可強制:CIP-21 hook 無平台機制 |
| C21 | drift | HIGH | AMM 平台原語 node 未實作 |
| C28 | secu | HIGH | CloseCard 對 Frozen card 允許——合規凍結被繞過 |
| C5 | drift | HIGH | Inline timer manifest——共識關鍵的 proposer-selection 機制規格完全缺 |
| secrets-WP | drift | HIGH | PROXY_SOAK_PERIOD 規格 86,400(≈30 天)vs 代碼 100 blocks |
| storage-WP | secu | HIGH | 私有 volume 的 PoR shard-inclusion proof 不可驗:加密 manifest 無法產生到 manifest_root 的 shard_hash Merkle 路徑 |
| C10 | drift | HIGH | opcode 160–164 與 Container Registry actor 0x11 上鏈缺,儘管副標「code-aligned v2」|
| C14 | comp | HIGH | PREMIUM 費用與 MIN_GATEWAY_STAKE 無預設值,阻礙上線 |
| C15-gw | drift | HIGH | static_volumes 部署期所有權驗證未實作;代碼 TODO 已證實 |
| C15-asset | secu | HIGH | Caller-Auth 簽名 preimage 未綁定 mounts 或 payment_proof(forward security 缺口) |
| changelog | comp | LOW | 6/12 changelog 的 IBE HKDF 金鑰派生漏規範性 salt 與 info 參數 |
| C1 | drift | MEDIUM | 規格的治理儲存 key namespace 與上鏈不符 |
| C1 | comp | LOW | 存的 max_fee_per_cycle 低於當前 basefee 時無 fire-time gate |
| C1 | comp | LOW | 錯誤碼 TimerRejectedBelowBasefee/TimerPriorityClampedAtSchedule/TimerArgDeprecated 不在錯誤登記表 |
| C14 | cons | MEDIUM | Query 路徑違規錯誤碼在 Part I 與 II/III 間更名無 deprecation |
| C14 | cons | MEDIUM | subdomain_policy 預設在 Part I 與 Part II 衝突 |
| C14 | cons | LOW | GatewayProfile stake_amount 型別在 Part I 與 II 不符 |
| C14 | drift | MEDIUM | ingress.http quota flag:代碼 quota=true,Part II/III 定 quota=false |
| C14 | drift | MEDIUM | RegistrySettlementConfig 缺 gateway_percent;儲存 key 與預設與 CIP-14 Part II 不符 |
| C14 | drift | LOW | Registry entry 數陳舊:CIP 說 14→17,代碼已 19 且含 ingress.http |
| C14 | comp | MEDIUM | Dutch auction 釋放價公式不完整;ERR_UNAUTHORIZED_GATEWAY/ERR_UNKNOWN_POOL 未定義 |
| C16 | cons | MEDIUM | dns.attach_external entitlement 描述為 target 需求,實作為 caller-delegation |
| C19 | comp | MEDIUM | MAX_TOOL_INPUT_BYTES_DEFAULT 標「治理預設」但無治理機制定義 |
| C22 | secu | MEDIUM | 無界 checkpoint list——O(auction_duration) 鏈上狀態成長 |
| C22 | comp | LOW | 為 CCA hook 陳述 hook gas cap 卻無強制機制 |
| C25 | secu | MEDIUM | B.4.4 gas grief 防禦對 L3 generic call(§3.4)無效 |
| C25 | comp | MEDIUM | §1.6 要求的 revocation-set 檢查不在規範 deliver() 偽碼 |
| C25 | comp | MEDIUM | L2-Deployment-Isolation 綁定機制不在 CrossChainMessage struct 與 deliver() 偽碼 |
| C25 | cons | LOW | §1.6 finality 述詞「finalized_height ≤ H」寫反 |
| C25 | drift | LOW | §1.6 引用的 GET /chain/finality endpoint 上鏈 RPC 不存在 |
| C25 | comp | LOW | WP-v2 r2 Delta 9 §16.z 是死引用 |
| C28 | comp | LOW | bank_activation_height 無指定 opcode 或設定治理機制 |
| C30 | comp | MEDIUM | storage_root proof 服務 RPC endpoint 被引用,但 CIP-15/CIP-17 皆缺 |
| C4 | secu | MEDIUM | 順序 DB commit 復原路徑留下未記錄的暫時不一致窗 |
| C6 | drift | MEDIUM | Verify builder 模式字串(tee/zk/optimistic/consensus)與上鏈 VerificationMode enum 變體不符 |
| design-decisions | drift | MEDIUM | EIP-1559 timer basefee 與 per-actor 公平權重被描述為「future」但已上鏈 |
| econ-fees | cons | LOW | State-rent 用 atto(10^18)精度,而 CBY 各處為 9 位(10^9 wei) |
| opcode-addr | drift | LOW | CIP-14/16 opcode 65/66/67(IngressDispatch/CompleteReceipt/ExternalDomainCallback)有規格但上鏈 codec 缺 |
| runner-storage | drift | MEDIUM | STORAGE_GRACE_EPOCHS:文件以 `_EPOCHS` 名給 block 數;代碼用實際 epoch(1-2) |
| runner-storage | drift | MEDIUM | cbfs 離線 repair/orphan 節奏以秒表達,與 CIP-9 區塊節奏分歧 |
| runner-storage | cons | MEDIUM | WP challenge/dispute window:散文「15 分」vs 參數 75 blocks 內部不一致 |

---

## 6. 碰撞掃描 — 未驗證

- 確定性掃描標出 **130** 條 opcode / 系統 actor 地址 / 常量值碰撞候選。其專屬對抗驗證 pass **未跑成**(兩次都被用量限額掐斷),故仍**未驗證**。
- 人工判讀:絕大多數為**良性的 per-CIP 枚舉 namespace 重用**(如 opcode 0x01–0x05 在許多本地指令枚舉重複出現;低位系統 actor 地址在示意表重複)。**不**計入確認發現。
- 真正的碰撞已獨立浮現並在上方確認集:**兩份都編號 CIP-15 的檔案**(`cip-15-gateway-implementation.md` vs `cip-15-public-asset-hosting.md`),以及 **CIP-13 v2 master opcode 表帶 CIP-10 陳舊 61–64 vs CIP-10 v2 的 160–164**。
- **建議:** 別再花一趟驗證,改用便宜法解決:直接從 `cowboy-protocol-codec` + `node/types/src/execution.rs`(單一真相源)生成 opcode/地址分配表,在 CI 對每份 CIP 宣稱的編號做 diff。

---

## 7. 方法與注意事項

- **管線:** 39 個 Sonnet 逐份審計(深讀 + 代碼落地漂移核對)→ JS 碰撞掃描 → 6 個 Opus 主題跨文件代理 → 2 視角 Opus 對抗驗證。Backfill:對每條 MED/LOW 跑 Sonnet 懷疑者 → Opus 確認者(短路)。
- **每條確認發現都需兩個獨立驗證者同意。** 對 top HIGH 的獨立 grep 抽驗(MIN_SELF_BOND_BPS / LANE_SYSTEM_CYCLES / STORAGE_FEE_*)全部屬實。
- **成本:** 兩趟工作流共約 1,211 個子代理、~44.8M token,且都在尾端撞用量限額(週限額 + session 限額)。未驗到的缺口:碰撞驗證 pass(§6)、23 條 MED/LOW 的第二視角(§5)。**依指示未再跑代理補這些缺口**,以低價值的 open gap 記錄之。
- **殘餘 false-negative 風險:** Phase-1 首過跑在 Sonnet;細微的跨文件密碼學問題可能仍未找到。本報告涵蓋已浮現並經驗證者確認者,非「不存在」的證明。

---

## 8. 15 條 HIGH 的逐條處置(2026-07-10)

每條經回一手規格+代碼原文研判,分三類。規格修訂 **[cowboy#239](https://github.com/cowboyinc/cowboy/pull/239) 已 merged**(main `0fab9ab`);後續小修 §5 pro-rata `0.89 → 0.88`(H-9 grep 漏的小數寫法)= **[cowboy#240](https://github.com/cowboyinc/cowboy/pull/240) 已 merged**。兩條代碼修復 **node#1004(H-1)、node#1005(H-11)皆 TDD + Marshal `pass`(run557/558)後 merged 入 `devnet`**(ae1c1540 / 474d2c85)。

### A. 已直接修規格(10 條)— 代碼為既成部署事實,規格寫錯/缺失

| # | 檔案 | 處置 |
|---|-----|------|
| H-4 | cip-25 §2.2 | nonce 連續分配但 L2 不強制投遞順序(只 exactly-once);與 §B.2 對齊,排序走 `send_stream` |
| H-5 | cip-26 §3.6 | gas 表改為上鏈值(base 200、per-byte 100、cells 無條件 200/byte、pin 300、load 1/53)+ amendment |
| H-6 | cip-3 §2.2.3 | lane 表 10M → 80M(User 22.2M/Runner 8.89M/Timer 8.89M/System 40M=2×target)+ amendment |
| H-7 | cip-3 §2.2.4.9 | 4096-bit MUST → SHOULD + 註「僅部署期靜態強制,運行期待 COW-970-類 follow-up」(另需 CODE 補 VM hook) |
| H-9 | cip-31 §4 等 | 費用拆分 10/1/89 → **10/2/88**(全篇,對齊代碼/CIP-9/測試) |
| H-12 | cip-8 §11/§12 | session ops 是 opcode 52–57 的 SystemInstruction;§12 重寫;提醒補 uniqueness 測試 |
| H-13 | design-decisions | 通脹曲線對齊技術 WP §8.2(8/6/4/3/2% floor) |
| H-2 | cip-15-asset §6 | 加 errata:上鏈為 v2(STORAGE_MANAGER 0x0A / opcode 102 / static+dynamic / ROUTE_PRIORITY_GAP) |
| H-3 | cip-20 | 補述三個上鏈指令 IncreaseAllowance/DecreaseAllowance/Permit(opcode 21–23、err 1413–1415、chain_id 綁定) |
| H-15 | storage-WP Create | 加 errata:DEK 封裝實為 CBSS 門限-IBE(committee epoch + release-key hash @ 0x04),非 HKDF |

### B. 須改代碼、規格是對的(2 條)— 已 TDD 修復 + Marshal 通過 + merged

| # | 判定 | 交付 |
|---|------|-------|
| H-1 | CIP-13 `MIN_SELF_BOND_BPS` 定義卻零強制 → delegation handler 補 self-bond 校驗(precondition 3b,u128 saturating,`cip13.min_self_bond_bps` governance-tunable;flag-day) | [node#991](https://github.com/cowboyinc/node/issues/991) → **[node#1004](https://github.com/cowboyinc/node/pull/1004) merged**(devnet ae1c1540) |
| H-11 | CIP-5 超預算 carry-forward timer 遺失 → Preserve `remove_timer`+rebucket 到 `current_height+1`(照 COW-2333 retry idiom;flag-day) | [node#992](https://github.com/cowboyinc/node/issues/992) → **[node#1005](https://github.com/cowboyinc/node/pull/1005) merged**(devnet 474d2c85) |

**A 收尾(Marshal 標的兩條殘留 — 調查後判定「已被既有代碼/測試覆蓋」,不加冗餘;僅補一條真缺的覆蓋):**
- **H-1 self-unbond/config 殘留 → 撤回(非 gap)**:runner 持有委託時無法降自質押破比例——full deregister 已被 `RunnerHasActiveDelegations` guard 擋(`registry.rs:284`,測試 `runner_deregister_blocked_by_active_delegations`),且**無部分自 unbond 路徑**(`self_stake_unbonding_claimable_at` 從不設 Some);config `max_delegated_stake` 不影響比例。
- **H-11 `TimerListFull`@(h+1) drop 殘留 → 撤回(已覆蓋)**:產生 `TimerListFull` 的 cap 已於 `timers.rs:419` 單測;Preserve drop arm 與已上鏈的 retry arm(COW-2298)結構相同。
- **真缺的覆蓋 → 已補**:H-1 測試原只覆蓋 delegate(`is_increase=false`);新增 `increase_self_bond_floor_enforced` 鎖住 increase 路徑 = **[node#1006](https://github.com/cowboyinc/node/pull/1006) 已 merged**(devnet 1a1def69)。

**終態:15 條 HIGH 全數落地** — 規格 10 條(#239+#240 merged)、代碼 2 條(#1004/#1005 merged,TDD+Marshal pass)、覆蓋補強 1 條(#1006 merged);餘 decision:#237 已 closed(resolved)、#236/#238 OPEN 待團隊裁決。

### C. 須團隊定奪(3 條)— 經濟/密碼/跨 CIP 設計,不替裁

| # | 判定 / 建議 | 追蹤 |
|---|-----------|------|
| H-8 | CIP-30 O(1) fork vs CIP-27 sealed 排除不可調和。建議方案 b(**runtime**(非 on_fork)刪 manifest-declared sealed keys),須兩份 CIP 協同 | [#236](https://github.com/cowboyinc/cowboy/issues/236) · 方案文檔 `refs/analysis/2026-07-12-cip30-cip27-fork-sealed-exclusion-decision.md` |
| H-10 | ~~CIP-31 儲存費 per-MiB vs 代碼 per-byte~~ **已解決**:devnet 代碼(`cowboy-protocol-types@0aa46e1`)`STORAGE_FEE_PER_MIB_PER_EPOCH = 450` = 規格;per-byte 常量全刪 | **[#237](https://github.com/cowboyinc/cowboy/issues/237) 已 closed(completed)** · 文檔 `...2026-07-12-cip31-storage-fee-denomination-RESOLVED.md` |
| H-14 | CBSS `MIN_PROXY_STAKE` 規格 10k vs 代碼 1k(10× Sybil)。建議方案 a(代碼調高至 10k,單位基準須釘)+ 綁 COW-2497 | [#238](https://github.com/cowboyinc/cowboy/issues/238) · 方案文檔 `refs/analysis/2026-07-12-cbss-min-proxy-stake-decision.md` |


---

## 9. Security MEDIUM 逐條驗證 triage(2026-07-12,vs current devnet/main)

18 條 security-維度 MEDIUM 全部回**當前源**核實。結論:**0 個 live 可利用 bug**——多數已解決(審計基於陳舊 base)、或代碼正確而規格沉默、或機制未上鏈。

| # | 條目 | 當前狀態 | 處置 |
|---|------|---------|------|
| 1 | CIP-31 challenge pool 下溢 | 代碼已正確 cap(`ras.rs:1212-1219`,`min(bounty, pool−reserve, epoch_cap−paid)`,無下溢/無 mint) | ✅ **spec 補全 [cowboy#241](https://github.com/cowboyinc/cowboy/pull/241) MERGED**(Marshal deep PASS run563;advisory:新行沿用 CIP-31 慣例 key `system:cbfs:*`,code 實為 `cip31.cbfs.*`@0x09=既有全域 namespace drift) |
| 2 | CIP-34 Intent 簽名 chain_id | **已解決**:r7 spec + 代碼(`settlement.rs:705`)綁**節點自身 chain_id**,非 tx.chain_id | 無需動作(stale) |
| 3 | CIP-34 RevealAuction wedge | **已解決**:r7 改為 `CancelledNoValidBid` cancel,不 wedge | 無需動作(stale) |
| 4 | CIP-12 CircuitBreaker 7-of-9 auth | **已解決**:`council.rs` 實作 Security Council 7-of-9 | 無需動作(stale) |
| 5 | CIP-16 Frozen-ACTIVE | 代碼正確:resolver 用 `expires_at <= block_height` 判 serveable,不看 stored status→過期綁定 resolve None,不可利用 | 低優先 spec 補全 |
| 6 | CIP-15 SSRF route_serving_endpoint | gateway 代碼已硬化(scheme guard+redirect-off+private-IP,gateway#35) | 低優先 spec 補全 |
| 7 | CIP-10 非-TEE billing full escrow | shipped-as-designed(測試 `container_billing_dispute_charges_full_escrow` 斷言此行為) | 設計 review,非 bug |
| 8 | CIP-10 CAP_NET_BIND_SERVICE 誤認 | 文檔/註解措辭問題 | 低優先 doc 修 |
| 9 | CIP-23 UpdateCollateral 無 ROOT_UPDATE_DELAY | ✅ **CONFIRMED live**(深挖):spec 三處 mandate `ROOT_UPDATE_DELAY`(§3.8.4/opcode126 表/Parameters「1 week」)但代碼**零強制**(常量不存在、handler 無 `effective_at >= block+delay`);system_deployers 可即時換 collateral,塌掉「UpdateCollateral 慢 / DeprecateBinding 快」兩層設計。**H-1 同型**(spec 安全參數定義卻不強制) | ✅ **已修 TDD** [node#1010](https://github.com/cowboyinc/node/issues/1010) → **PR [node#1011](https://github.com/cowboyinc/node/pull/1011)**:加 `ROOT_UPDATE_DELAY_BLOCKS=604_800`(gov-tunable)+ handler enforce `effective_at >= block+delay` + 穿 block_height;測試 too-soon 拒/邊界 accept/tunable;1787/0;flag-day |
| 10-14 | CIP-12 §7.4.b unlimited-gas migration / CIP-18 method=cowboy chain_id / CIP-22 double-finalize / div-zero / front-run | **機制未上鏈**(§7.4.b external;payments/auctions handler 未建) | spec-design:實作前先在規格加安全要求 |
| 15-17 | CIP-28 locked_after_transfer / fee_payer_override wire / CIP-33 IBE label | **未上鏈**(cards/trading-post 未建) | spec-design,實作前補 |
| 18 | secrets-WP HEALTH_RECOVERY_BPS_PER_BLOCK | 確認代碼**未實作** | doc-status:標未實作 or 補實作 |

**唯一需進一步看的**:#9 CIP-23 UpdateCollateral 的最小延遲(治理信任 MEDIUM)。其餘要麼已解決、要麼代碼正確、要麼未上鏈(spec-design,待實作時處理)。

---

## 10. §5 需人工裁定 — CRITICAL/HIGH 逐條破驗證者分歧(2026-07-13,vs current devnet/main)

§5 的 50 條驗證者分歧中,報告明文標「含數條 CRITICAL/HIGH 安全項,優先人工看」。對其中 **2 條 CRITICAL + 15 條 HIGH** 全部回**當前源**(node devnet `1a1def69` / cowboy main `d8a5d44`)以雙視角深挖破分歧。結論:**0 個 live 可利用 CRITICAL/HIGH bug**——最嚴重的兩條 CRITICAL 一條是 spec 殘留(errata 漏一節)、一條機制未上鏈;HIGH 全部落在「代碼正確 spec 過度承諾 / 已被 read-time 防護 / 未上鏈 / 決策值漂移」四類。**本輪產出 6 處 spec 修正**(cowboy repo),無代碼 bug 待修。

### A. 2 條 CRITICAL

| # | 條目 | 裁定 | 處置 |
|---|------|------|------|
| C25 | runner 委員會 attestation 未認證 `state_root` | **NOT-ON-CHAIN**:CIP-25 L1 anchor 路徑(`IChainAnchor`/`BlockCommitment`/`Anchor.v1` 簽名)node/runner **零實作**;唯一跨鏈 inbound(CIP-34 `IntentCreditDeposit` opcode 151)是 stub 回 `UnsupportedInstruction`(`system_instruction.rs:1307`)。`state_root` 在 spec 是 opt-in by-design;無部署代碼可偽造。但發現一條真的 spec 缺陷:`IChainAnchor.commitment()` 回傳 `stateRoot`,而 §1.5 的 `Anchor.v1` preimage 卻不含它——**若某 deployment 發佈 state_root,委員會簽名不認證它=可偽造**。 | ✅ **spec 修**:CIP-25 §1.5 加 normative 條款「preimage MUST 綁定 deployment 發佈的每個 root(`… ‖ receipt_root ‖ state_root ‖ parent_hash`,只 append 實際發佈者)」+ 標明未上鏈=build-time 要求。留給 M2/v2 實作者的 review gate。 |
| storage-WP | `account_secret` 未定義,DEK 封裝模型不可實作 | **RESIDUAL-GAP**:與 H-15 同根,但 H-15 errata(line 398)只覆蓋「Create」節,**漏了 §3.1 DEK generation(line 729)** 那條獨立 normative MUST——仍引用未定義的 `account_secret` HKDF。鏈上實為 CBSS 門限-IBE(`ras.rs`)。 | ✅ **spec 修**:§3.1:729 加 superseded marker(對齊 line 398 errata,指向 CBSS committee key material),劃掉 HKDF/account_secret 句。 |

### B. 深挖的 6 條 HIGH

| # | 條目 | 裁定 | 處置 |
|---|------|------|------|
| C2 | EconomicBond 目標驗證未實作 | **SPEC-OVERSTATES**:代碼 as-designed(`verifier.rs:1409` trust-first 單結果,`runners_to_slash` 恆空;dispatch 有 1.5× stake 過濾但非 per-result bond)。CIP-2 §729 已誠實記錄,唯技術 WP §9.2 表仍寫「Objective checks」。 | ✅ **spec 修**:技術 WP §9.2 `economic_bond` 行改 trust-first + errata 註,對齊 CIP-2 §729。 |
| C5 | inline timer manifest / proposer-selection 規格缺 | **CONFIRMED-GAP(部分)**,MED-HIGH drift:無「proposer 選擇」自由(firing 是 state-deterministic FIFO,已由 §5.1/§6.5/§7 覆蓋),但 **(a) inline timer manifest**(`inline_timer_ids` 進 block digest preimage,`speculative.rs:1444`)+ **(b) carry-forward `skip_count` rebucket→next height + dead-letter@256**(進 state_root,H-11/#1005 修的)**CIP-5 完全沒寫**→spec-only client 對不上 block hash / state。 | ✅ **spec 修**:CIP-5 加 §7.1「Inline Timer Manifest(block-digest commitment)」+ §6.5 補 carry-forward/rebucket/dead-letter(`TIMER_MAX_CARRY_FORWARD=256`/`MAX_INLINE_TIMER_MANIFEST_IDS=4096`)。 |
| C15-gw | static_volumes deploy-time 所有權驗證未實作 | **PARTIAL/DEFENSE-IN-DEPTH → 降 MED/LOW**:deploy-time TODO 屬實(`system_instruction.rs:5181`,`validate_route_volumes` 已寫未接線),但 read-time 已擋跨 owner 私有資料攻擊:gateway 用**發佈 actor 自身 owner** 派生 volume_id(`gateway-server/lib.rs:1218`)+ **Public-only gate**(`gateway-cbfs/lib.rs:402`)。已被 escape `cow1293-sec-6-8` 追蹤,合理 blocked(binding 無鏈上表示)。 | 無需動作(降級記錄);unblock 後接 `validate_route_volumes`。 |
| storage-WP | 私有 volume PoR shard-inclusion proof 不可驗 | **STALE/REFUTED**:安全宣稱破產。鏈上 PoR 錨在 `StorageCommitment.shard_root`(密文 `chunk_root` 的 keyed sparse Merkle,`por.rs:271`/`ras.rs:3670`)**非** `manifest_root`;因 `encrypt→erasure→hash`,所有 proof 輸入皆公開密文承諾→**私有 volume PoR 無需 DEK 完全可驗**。但 WP PoR 散文(§7.3/lines 527-540)仍寫 `manifest_root` 兩層鏈=真的 doc-drift。 | ✅ **spec 修**:WP PoR 節改為 `shard_root` over `chunk_root` accumulator + note 澄清密文承諾/DEK-independent。 |
| secrets-WP | PROXY_SOAK_PERIOD 規格 86,400 vs 代碼 100 | **DECISION-VALUE-DRIFT**:代碼 `cbss.rs:85`=100,CBSS flag-flip 治理提案明釘 100 為 launch 值→代碼=治理決定;WP 86,400 與 §3 audit 引的 216,000 皆 stale narrative。同 MIN_PROXY_STAKE(#238)家族的反-Sybil 經濟參數,**不替裁**。 | ✅ **spec 修(僅記漂移不改值)**:secrets-WP §13 表頭加 value-drift errata(PROXY_SOAK=100 deployed / MIN_PROXY_STAKE=1000 deployed 綁 #238),標「部署值 authoritative,mainnet 目標待治理」。 |

### C. 批次 triage 的 9 條 HIGH(未上鏈 / 決策)— 逐條回 grep 定性

- **C18 ×3**(BridgeEvidence single-sig / credit_inbound unbacked mint / Query 雙重服務)= **NOT-ON-CHAIN**:`BridgeEvidence`/`facilitator`/`credit_inbound` 在 node/runner 源碼**零命中**;PaymentGate `0x12` 僅地址保留(`system_actors.rs:71`),無 handler/opcode。CIP-34 `IntentCreditDeposit` 是**另一機制**且為 stub。
- **C21 ×2**(hook gas cap 不可強制 / AMM 原語未實作)= **NOT-ON-CHAIN**:`liquidity_pool`/`amm`/`pool_hook`/`Swap` 源碼零命中(勿與已實作的 CIP-20 `token_hook_max_cycles=50_000` 混淆)。
- **C28**(CloseCard 繞過 Frozen)= **NOT-ON-CHAIN**:`CloseCard`/`agent_bank` 零命中(`card` 命中皆 rate-**card** 誤判)。
- **C10**(opcode 160-164 + Container Registry 0x11 缺)= **confirmed-absent(drift 準確)**:最高 System opcode 是 159;Container Registry 實在 **0x13 非 0x11**(0x11=VALIDATOR_SET)。
- **C14**(PREMIUM/MIN_GATEWAY_STAKE 無預設)= **NOT-ON-CHAIN(真 spec gap 但功能未建)**:`MIN_GATEWAY_STAKE` 源碼零命中,無 `register_gateway` handler,`GATEWAY_REGISTRY 0x0F` 無寫入路徑。
- **C19**(x402_compat vs CIP-18 §13.6)= **NOT-ON-CHAIN spec-vs-spec**:`x402` 零命中;兩份規格皆未實作,紙面 reconcile 即可。

**處置**:未上鏈群依 §9 先例(spec-design,實作前先在規格加安全要求),於各自 CIP 實作 PR 的 review gate 處理,本輪不預先改 spec。C14 gateway 若近期上線需先釘 `MIN_GATEWAY_STAKE`/PREMIUM 預設。

### 終態
- **6 處 spec 修正**(cowboy repo):storage-WP §3.1 + PoR 節、技術 WP §9.2、CIP-25 §1.5、CIP-5 §6.5+§7.1、secrets-WP §13 errata。
- **0 條代碼 bug**(對比 §9 抓出的 #9 CIP-23 live bug,本 §5 CRITICAL/HIGH 批次無 live 代碼缺陷)。
- **1 條降級**(C15-gw HIGH→MED/LOW,已 escape 追蹤)。
- **未上鏈群**(C18/C21/C28/C10/C14/C19)= spec-design,待各功能實作時在 PR review 補安全要求;C25/C5 的 build-time 要求已寫進 spec 供未來實作者。
- 剩 §5 的 MED/LOW(~30 條)未在本輪範圍。

---

## 11. §6 碰撞掃描收口(2026-07-13,cheap CI-diff 法,零 agent)

依 §6 建議「別再花一趟驗證,改從 `cowboy-protocol-codec`+`system_actors.rs` 生成權威表在 CI diff」。已實作:`refs/analysis/check_alloc.py`(自含,workspace root 跑,對每份 CIP 掃 opcode/地址數字宣稱 diff 權威源,exit≠0 on mismatch=**可直接當 CI gate**)。

**權威源自身零碰撞**:143 個 SYS_ opcode(range 0–159,`#[deny(unreachable_patterns)]` 編譯期保證)+ 21 個 system actor 地址,皆無重號。故 §6 的 130 候選確為良性 per-CIP 枚舉重用(人讀已判)。

**撈出 1 條真跨-spec 碰撞**(§6 未驗批的真發現):**WP §9.1「canonical」地址表 vs 部署代碼在 `0x11`/`0x13` 系統性衝突** —— 表寫 `0x11`=Container Registry / `0x13`=BankActor,代碼實為 `0x11`=**VALIDATOR_SET**(genesis 部署)/ `0x13`=**CONTAINER_REGISTRY**(Council-pausable),且 VALIDATOR_SET 整個不在表內;cip-10/14/16/18/34 全跟著誤放 Container=0x11。方向由 WP §9.1 自身 note 1/2 鎖定(部署 registry=source of truth、deployed claim wins)→**spec 須跟上**。**已修**:WP §9.1 錨表 + cip-14/16/18/34(Container 0x11→0x13、補 VALIDATOR_SET 列)。**CIP-10 Container=0x11×8→已修 0x13**(✅ RESOLVED 2026-07-14 owner-authorized 破例 = cowboy#260;最後一個 holdout 閉合)。**BankActor(CIP-28)撞 0x13→已重分配 0x16**(✅ RESOLVED 2026-07-14 owner-approved;留 0x15 給 penciled EventListener,next free=0x17;WP §9.1 + CIP-28 已修 = cowboy#259)。詳:`refs/analysis/2026-07-13-system-actor-address-reconciliation.md`。

**其餘掃描項=良性/已知**:`SYS_VALIDATOR_*`(cip-11)/`SYS_SESSION_*`(cip-8)是正確 prose(前明說不存在/後須納入測試);`SYS_FETCH_SECRET_METADATA`(cip-24)是 host syscall 非 wire opcode;dual cip-15 + CIP-10 opcode 61-64 vs 160-164 已在 §2/§3 記錄。

### §6 終態
- **checker 落地**(check_alloc.py)= CI seed,現跑綠(CIP-10 holdout+benign 例外已標註)。
- **7 處 spec 修正**(WP §9.1 + cip-14/16/18/34 地址 + reconciliation doc)= 本輪第二個 cowboy PR。
- **CIP-10 Container=0x11×8 已修**(0x13,cowboy#260,owner-authorized);**BankActor 重分配已閉環**(0x16,cowboy#259)。地址表全部與部署代碼一致。

---

## 12. §3 drift 長尾 — state-layout 群(2026-07-13,cowboy#248)

§3 drift 長尾教訓:**每條回當前源核實**(審計 base 陳舊,值可能早改)。優先 fork-class。

**CIP-4 storage(9 條 §3 drift + 1 條 §4 LOW,全 code-verified 為當前值非 stale)= 最高值,一個 agent 抽全子系統 ground truth(權威源=`node/storage/src/state_key.rs::StatePrefix` enum 0x01–0x1D 28 個,**無 0x00**)後逐條修**:
- §4.2 prefix 表整表換(舊 0x00–0x0D 錯位→權威 0x01–0x1D,補齊 16 個缺的 0x0E–0x1D):actor code content-addressed@0x0F(非 per-addr)、timer index=keccak256(height)(非 raw)、Account=0x01、SystemState=0x0A。
- §4.1/§2:key layout `[1B][20B addr][33B slot]`(20-byte 非 21-byte)。
- §4.3:mailbox=individually-keyed FIFO ring(0x04‖be(seq))+head(0x10)/tail(0x11)指標,非 VecDeque blob。
- §5.3:receipt_root=commonware-codec `encode()` 非 RLP(merkle_utils.rs)。
- §11:SNAPSHOT_INTERVAL_BLOCKS=100_000 非 1024。
- §12.5:rent 參數=單一 merged `RentConfig` blob@`system:cip4:rent_config`(非五 key);部署 rent_rate_atto=2_739_726_027_397_260(≈1 CBY/byte/year=舊 0.001 的 ~1000×,WP §13.1 已認;經濟目標由監控帶治理)+補第六欄 bond_rate_atto。

**CIP-29 event-hooks(prefix drift,用同一 ground truth 直接修)**:EventSub/EventSubIndex 實為 **0x18/0x19**(非 0x14/0x15=CIP-26 Library/ActorLibPin);prefix 分配到 0x1D(非 0x13)。

**交付 cowboy#248**(cip-4 + cip-29,base main)。**教訓:state-layout 這種同子系統多條 drift,派一個 agent 抽全 prefix/常量權威表比逐條跑更省;prefix 表是 light-client fork-class 最高值**。

**CIP-24 secrets(CBSS 群,cowboy#249)= 第二群,同法一個 agent 抽全 CBSS 常量/domain/opcode ground truth 後修**:
- **1s/block 確認**(BLOCKS_PER_YEAR=31,536,000、1天=86,400):多條 12× drift 根因=spec 用 12s/block 算 block 數。加 §4.2 normative 基準註。
- **機械值修**(code 權威):REQUEST_FRESHNESS 32→384(=32×12,同 wall-clock)、LIVENESS_RESPONSE 100→64;重算 MIN_CHALLENGE_DELAY=416/MAX_AGE=480 註解。
- **決策 errata 不改值**:PROXY_SOAK code=100(devnet-short)、RESHARE_INTERVAL code=1,296,000(demo ~15天,prod 目標 ~6mo)、MIN_PROXY_STAKE=1,000(#238)、GOVERNANCE_REVIEW=2,592,000(#243 處理,不重編)。
- **interop 修(最高值)**:RotateCommittee 簽名 spec 用兩 domain(cbss/dkg-commit/v1+cbss/reshare-zeroize/v1,u64_le)→code 用**單一 `cbss/rotate-committee/v1`** 兩委員會同簽一個 BE `rotate_hash`;照 spec 實作簽名不驗=跨實作不相容。修 canonical-payloads 節+兩處 struct field。
- **completeness**:補 opcode 82(ExpireLivenessChallenge,permissionless)/83(RequestReshare,owner-only)/84(ForcedDeregisterCbssProxy,gov-only)的 §3.5 body。

**教訓:CBSS 這種「多值 12× + 一個 interop domain + 缺 opcode body」混合群,仍是一個 agent 抽全 ground truth 最省;RotateCommittee domain 這種跨實作簽名不相容=比純值 drift 高一級,務必修**。

**CIP-12 governance(cowboy#250)= 第三群。headline:spec 描述的治理系統遠比部署豐富——migration upgrade + stake-weighted voting 未上鏈,tally fail-closed(讀 spec 會嚴重高估 live)**:
- **[STALE-AUDIT 駁回]**:地址範圍 code 用 allowlist `{04,05,06,07,08,0C,0D,0E,0F,10,13,14,1D,1E}`(pause.rs is_pausable_actor,含已部署 0x0E-0x10/0x1E),非 audit 說的 0x01-0x0D;CircuitBreaker 7-of-9 已上鏈(council.rs,genesis SignerSet)非 external(audit 看的是 stale code 註解)。
- **[LIVE-DRIFT 修]**:ProposalId u64 單調計數(非 bytes32)、BasefeeConfig@0x06/system:basefee_config(非 0x09.params)、UpgradeSystemActor payload 僅 {target,new_code_hash,activation_delay,rollback_window}(無 code_ref/migration/spec_ref)、無 governance-specific error codes(僅 generic 1211/1213/1219)。
- **[NOT-IMPL 標註]**:§7.4.b migration 路徑整個未上鏈(enact 僅寫 code_hash pointer)→補 normative gas-cap 要求(禁 unlimited gas,防無窮迴圈停產);§6 stake snapshot 未接(COW-1028)→voting_snapshot_total=0→resolve fail-closed Defeated(治理 inert)+ tally 是 1-per-address 非 stake-weighted;§5.2 timing demo-scale(TEMP_CHECK=100/timelock 5-14 blocks)。
- 加多個「⚠️ On-chain status」callout(§6/§7.1/§7.4.b/§5.2)標 deployed vs 設計。

**教訓:治理這種「大量 spec 是設計、少量已上鏈」的 CIP,agent 的 [LIVE-DRIFT]/[NOT-IMPL]/[STALE-AUDIT] 三分類最關鍵;修法=inline 修 live-drift 值 + 加 on-chain-status callout 標 not-impl,別刪設計(是 intended future);not-impl 的 security 項(unlimited-gas migration)把要求寫進 spec 供未來實作**。

**CIP-16 + CIP-2 群(cowboy#251,並行雙 agent)**:
- **CIP-16**:DomainBinding = 9-field code struct(enum serde 字串非 u8);**NamespaceKind={Actor,Gateway}**(routing-target)非 {COWBOY_NETWORK/FIRST_PARTY/EXTERNAL}(後者是 TldKind);owner/registered_at/expires_at 在**分離的 TldLabelRecord**(cip16:label:<fqdn>)非 binding;settlement key=`system:cip16_registry_settlement`;registry=19 entries(非 14→17,ingress.http 已部署);Frozen-ACTIVE [STALE-AUDIT] 不可利用(resolver lazy 查 TldLabelRecord.expires_at,external reverify 未上鏈)。修 Part II schema+§12 constants(Part I 是 verbatim v1 歷史記錄,靠 conflict rule 不動)。
- **CIP-2**:CrashAttestation → **SubmitCrashAttestation instruction(opcode97,{job_id,crash_signal})** 無獨立 struct(runner=tx.from);§7.2 EntitlementGrant/Delegate/CreateRole 用 typed Scope/Action/Constraints 非 Vec<u8>(codec 核實 opcode30);**aggregator_timeout_blocks 不存在**(fallback 走 JobSpec.timeout_blocks,AggregatorConfig 僅 {eligibility_percentile,bonus_bps});補 opcode 94-100 枚舉(94 Reputation/95 Aggregator/96 Slash/97 CrashAttest[runner]/98 NonReveal/99 Committee/100 SemanticSim,gov-only 除 97)。

**CIP-12 §1 abstract 一致性 follow-up(補進 #250)**:§7.2 修 allowlist 後,§1 abstract 仍說「0x0E-0x13 not yet in code」矛盾→改為部署 registry 實況(0x01-0x11 code-deployed,0x13/14/1D/1E 亦部署)。**教訓:改地址範圍時掃全 CIP 同一 CIP 的其他 section(abstract/table/prose)避免自相矛盾;linter frontmatter 會顯示舊版是因 checkout 別分支,非丟失**。

### §3 drift 交付累計(本 session)
- **#248** CIP-4 state-layout + CIP-29 prefix · **#249** CIP-24 CBSS · **#250** CIP-12 governance(+abstract) · **#251** CIP-16 + CIP-2 · **#243** CIP-3 KV + CIP-24 GOV_REVIEW(**全數 MERGED**,見 §13 ledger)

**cross-topic WP-vs-code 群(cowboy#252,並行三 agent,stacked on #247)**:三份白皮書(secrets/storage/technical)全量抽 WP 宣稱常量 vs 代碼實值:
- **secrets-WP**:§8 gas 表整表修(CBSS_GAS_* 實值,舊值高 4-80×);MAX_SECRETS 1024→256、MAX_VERSIONS 256→32;health §9.2 LIVENESS_UNANSWERED 250→100、slash health 2500→per-class(500/500/5000)、HEALTH_RECOVERY not-impl;§13 LIVENESS_CHALLENGE_MAX_AGE 86400→480、RESHARE 86400→1,296,000、DKG_FINALIZE~2h;標 not-impl(HEALTH_RECOVERY/SLASH_WINDOW=permanent tombstone/PROXY_UNBOND=immediate/MAX_COMMITTEE_N=unenforced)。
- **storage-WP**:CapToken TTL 300s→900s/14400s→86400s、clock-skew ±60→±30(+WP 內部矛盾);**fee-split errata:code 現 10/1/89(PR#231@2026-07-10)→WP 90%/2% stale,且 CIP-31 §4(#240 的 10/2/88)反被弄 stale,須 re-reconcile 到 10/1/89**;STORAGE_GRACE_EPOCHS=1 epoch(非 7200 blocks)、POR_CHALLENGE_INTERVAL 600→7200、MAX_VOLUME_NAME 64→256、DEK client-generated(chain 只驗 wrapped_dek)、block-time+erasure errata(7200 blocks=~2h 非 24h;on-chain gate 收 K=1/K+M≤32,cbfs-lib 嚴界僅 client)。
- **technical-WP**:max_tx_size 128KiB→1MiB、per_actor_per_block_cycles not-enforced、emit_event 0cyc+1cell/byte(audit 說 neither 於 cells 是 stale)、mailbox 1M bytes→1000 messages、dedup 10000-block→500000 LRU、§13 lane% 5/20/25/50→50/27.8/11.1/11.1、challenge window 15min→75 blocks(~75s)、補 §3.1 PVM 4096-bit int cap(MAX_INT_BITS)。

**教訓**:(1)WP gas/常量表整表 stale 是常態,一個 agent 抽全 WP-vs-code 對照最省;(2)**經濟值會移動**——fee split code 從 88/2 又改成 89/1(PR#231),我之前 #240 把 CIP-31 改成 88/2 反成 stale=**别追移动的经济值,标 errata+coordination flag 让治理定**;(3)audit 的「code charges neither」可能自身 stale(emit_event 現收 1 cell/byte);(4)stacked PR:base=#247 分支 diff 才只顯示 WP delta,#247 merge 後 rebase onto main。

### ⚠️ 待 follow-up
- **CIP-31 §4 fee split re-reconcile 10/2/88→10/1/89**(code PR#231 移動;經濟值,交團隊協調,#252 只在 storage-WP 加 errata flag,未動 CIP-31)。

### §3 drift 長尾剩餘(未做,供後續)
單一 CIP 零星項(CIP-1/7/9/11/21/22/23/26/28/33 的 API 名/事件名/單值 drift,多為 §3/§4 LOW)未逐一過。主要 drift 群(CIP-4/24/12/16/2/state-layout + 三 WP)已全數處理。餘為長尾 LOW,建議交團隊照報告 §3/§4 spec-cleanup 或按需單點。

---

## 13. Campaign 收尾(2026-07-13)

深度審計後續處理 campaign 收尾。**方法定型:每群一個(或並行多個)agent 回當前 devnet 抽 ground truth → 逐條四分類(LIVE-DRIFT 值修 / NOT-IMPL 標註 / STALE-AUDIT 略 / DECISION-VALUE errata 不替裁)→ spec 修 → PR + 報告回填**。

### 全部 PR(cowboy,docs-only,無代碼行為變更)— **8/8 已 MERGED(2026-07-13)**
| PR | 範圍 | 狀態 |
|----|------|------|
| #247 | §5 CRITICAL/HIGH(6 修)+ §6 地址表(7 修)+ WP errata base | ✅ MERGED |
| #248 | §3 CIP-4 state-layout(9)+ CIP-29 prefix(3) | ✅ MERGED |
| #249 | §3 CIP-24 CBSS(值 4 + RotateCommittee domain + opcode 82-84 body) | ✅ MERGED |
| #250 | §3 CIP-12 governance(live-drift 4 + not-impl 標註 + §1 abstract) | ✅ MERGED |
| #251 | §3 CIP-16 domain schema + CIP-2 wire/opcode | ✅ MERGED |
| #252 | §3 cross-topic 三 WP 常量(原 stacked on #247→#247 merge 後 rebase onto main) | ✅ MERGED |
| #243 | §3 CIP-3 KV read + CIP-24 GOVERNANCE_REVIEW | ✅ MERGED(Marshal deep PASS run562) |
| #241 | §9 CIP-31 §7 pool-bounded challenger bounty(補全 challenge-pool underflow) | ✅ MERGED(Marshal deep PASS run563) |

**全部併入 origin/main。** #243↔#249 都改 cip-24 但不同行=零衝突並存。#252 rebase 手法:`git rebase --onto origin/main <old-#247-tip>` 只重放 WP commit + `gh api PATCH pulls/252 base=main`。

### 已處理範圍
- **§5**(2 CRITICAL + 15 HIGH 驗證者分歧)= 0 live bug,全 spec 修/降級/未上鏈標註。
- **§6**(碰撞掃描)= CI-seed checker `check_alloc.py` + 撈出 0x11/0x13 地址表真碰撞並修。
- **§9**(18 security MEDIUM)= 0 live bug 除 CIP-23 UpdateCollateral(node#1011 已 TDD 修)。
- **§3 主 drift 群**(CIP-4/24/12/16/2 + 三 WP + state-layout)= 全數處理。
- **15 HIGH**(§8)+ **top-5**= 前期已閉環(#239/#240/#1004/#1005/#1006/#1008/#1009/#1011)。

### 待團隊 follow-up(不替裁)
- **CIP-31 §4 fee split re-reconcile 10/2/88→10/1/89** → **[cowboy#253](https://github.com/cowboyinc/cowboy/issues/253)**(code 現 10/1/89,經 COW-938/#957 已 governance-tunable;#252 storage-WP 已 errata flag;含 CIP-31 逐處行號 + CIP-9 §5.6 + 決策項「89/1 是否 intended target」)。
- **3 decision**(#236 CIP-30/27 fork、#238 MIN_PROXY_STAKE、~~#237 已 closed~~)。
- ~~BankActor(CIP-28)地址重分配~~ ✅ **已決 0x16**(2026-07-14 owner-approved;WP §9.1 + CIP-28 = cowboy#259;0x15 留 EventListener)。
- ~~CIP-10 Container=0x11×7 待 owner 修~~ ✅ **已修 0x13**(2026-07-14 owner-authorized,cowboy#260)。
- 單一 CIP 零星 LOW 長尾(API/事件名/單值)交團隊 spec-cleanup。

### 前期彙整(存查)
- #248:CIP-4 state-layout(9)+ CIP-29 prefix(3);#249:CIP-24 CBSS;#243(既有):CIP-3 KV + CIP-24 GOVERNANCE_REVIEW。決策/errata:PROXY_SOAK、RESHARE_INTERVAL、MIN_PROXY_STAKE(#238)、rent_rate、fee-split(經濟)。

---

## 14. §3 drift 單一-CIP 長尾(2026-07-14,on-chain CIP 群)

§13 遺留的「單一 CIP 零星 §3/§4 drift」長尾接手。同法:**每 on-chain CIP 一 agent 回當前 devnet(node `2bb1eddd`)抽 ground truth → 四分類 → spec 修**。**scope 判準:只做機制已上鏈的 CIP**(CIP-1/7/9/11/23/26);未上鏈的 CIP-21(AMM)/22(拍賣)/28(銀行卡)/33(trading-post)依 §9/§10 先例留 spec-design、實作時在 PR review 補;**CIP-10 迴避令不碰**。

### 交付(cowboy branch `cbd/cip-longtail-drift-reconcile`,base main `1f15ac1`,docs-only)
| CIP | 處置 | 分類 |
|-----|------|------|
| **CIP-1** 排程器 | LANE_TIMER_CYCLES `2,000,000→8,888,890`(live,FIFO 路徑實用);刪「governance-tunable via TimerConfig」偽稱(TimerConfig 無 lane 欄=compile-time 常量);gov key namespace `system:cip1:*→system:gov:param:cip1.*`(gov_param_key 慣例)×3;加**一則合併「Implementation status」callout** 標 v3 auction 整組 gated-off(`H_v3=u64::MAX`):p50 tip 未接線、custom bid 未上 Python binding、三層物理結構未實作、schedule/fire-time basefee gate + 三 error code 未上鏈、W(actor) median 實走 competing-set | 2 LIVE-DRIFT 值 + 5 NOT-IMPL(合併 callout) |
| **CIP-7** stream | **無修**:SUBSCRIBER_PAID 路徑**完整上鏈**(`stream_key_manager.rs:263 acquire_epoch_access` + host fn `pvm_host.rs:4248` + SDK + 回歸測試 `cip7_stream_sdk.rs`),host/SDK 簽名與 spec §163-166 逐字一致 | STALE-AUDIT(駁回) |
| **CIP-9** runner storage | `RelayNodeProfile` schema 整塊重寫對齊 `node/ras/src/types.rs`(`stake_amount u256→u128`、`region_hint bytes4→region Option<string>`、`last_heartbeat→updated_epoch`、刪 `health:u8`→`status:RelayStatus`、補 owner/node_id/pubkey/endpoint/epoch/drain/rebalance 12+ 欄);health-decay 模型從未部署→改述 status+heartbeat-freshness+auto-drain(§5.2/§5.3);`STORAGE_GRACE_EPOCHS 86,400→1`(單位 epoch 非 block)+ `VOLUME_DELETE_GRACE_EPOCHS`;repair/orphan 常量 `_SECS` 化(300s/86,400s,off-chain wall-clock 非 block);mermaid「health decay→drain policy」 | 4 LIVE-DRIFT |
| **CIP-11** connectivity | `LIVENESS_TIMEOUT_BLOCKS=100` 更正為**生產 per-job timeout 預設**(非 test fixture);`mru_key`/`MruRecord` 加 NOT-IMPL callout(§9.2 present-first v3 已上鏈但 mru 遞歸權重未部署)| 1 LIVE-DRIFT + 1 NOT-IMPL;`PresenceInput` 塊欄/`SubmitPresenceCertificate` opcode/`ConsumedSeedsV1` MinPk 三項 STALE-AUDIT(spec 本已正確:PresenceInputV1 已上鏈共識欄、Mode-A/MinPk 皆已標 deferred+scheme_id 遷移)|
| **CIP-23** TEE | 加 §3.4「Wire encoding」normative 註:**無 `TeeAttested` enum tag**——TEE 走 `tee_required:bool`+`required_tee_type`,`TeeAttested`/`Deterministic` 是 philosophy 非 VerificationMode tag(tags `None=0..SemanticSimilarity=5`)| 1 LIVE-DRIFT;UpdateCollateral ROOT_UPDATE_DELAY 已 node#1011 修=STALE-AUDIT/RESOLVED |
| **CIP-26** libraries | `cells_per_pin §3.4 32→64`(對齊 §3.6+`gas.rs`);`code_size u64→u32`;§3.6 補 `MAX_LIBRARY_CODE_BYTES=131_072`/`MAX_TOTAL_LIB_BYTES=131_072` normative 上限 + `LibCapExceeded`;§3.7 補 `LibraryRemoved` event wire layout;§8 傳遞性 import overclaim 更正(§3.4 只掃 actor 自身 AST,library 私有依賴不自動解析)| 5 LIVE-DRIFT(2 值 + 3 doc-gap/overclaim)|
| **WP**(technical)| 殘留:abstract line 71「15-minute challenge window」→`DISPUTE_WINDOW_BLOCKS=75`(WP §5/§8 早已 reconcile,此為漏網 abstract 一處)| LIVE-DRIFT |

### 附帶撈出(非 spec,交團隊)
- **CIP-7 code bug**:CLI 範例 actor `node/cli/actors/stream_actor.py:30` 寫死 `STREAM_KEY_MANAGER_ADDR=0x12`,canonical SKM=`0x0D`(`node/ras/src/system_actors.rs:22`)。只影響該範例的直接 `call_actor` fallback(權威 `acquire_epoch_access` 走 host fn 繞過);非 spec drift,建議另開 code ticket。

### 教訓
- **on-chain-status callout 合併優於散點**:CIP-1 v3 auction 整組 gated-off,一則 abstract 後的合併 callout(標 `H_v3=u64::MAX`)比 6 處散注乾淨,且照 CIP-12 先例「別刪設計、標 not-impl」。
- **STALE-AUDIT 佔比高**:CIP-7 全條、CIP-11 三/四條、CIP-23 一條駁回——首過 Sonnet audit 對「已上鏈但 base 陳舊」與「spec 本已標 deferred」誤報率不低,長尾務必回一手源逐條核。
- **struct schema drift 是 wire/light-client class**:CIP-9 RelayNodeProfile 差 12+ 欄+3 型別=照 spec 反序列化必失敗,值最高;抽 Rust struct 原文整塊換最省。

### 剩餘(交團隊)
- 未上鏈 CIP-21/22/28/33 的 §3 drift + 安全項:實作時 PR review 補(§9/§10 先例)。
- CIP-10 §3 drift(opcode 160-164 / Container 0x11):迴避令,owner 修。
- CIP-7 範例 code bug(上「附帶撈出」):另開 code ticket。

### 14b. A1(on-chain drift)+ A2(spec-internal 矛盾)批次(2026-07-14,cowboy#258)

接續 14a,清「on-chain CIP 剩餘 drift(A1)」+「純 spec-internal 矛盾(A2,不依賴代碼)」。並行 6 agent,同四分類法。**docs-only**。

**A1 — on-chain drift(改 spec 對齊代碼):**
- **CIP-5** — Timer struct 補 4 個序列化上鏈欄(skip_count/retry_count/max_fee_per_cycle/max_priority_fee_per_cycle);codec 註更正(v5,前向相容 read,無需 wipe);schedule_timer_ex 補 2 host fee 參數(Python binding 層 NOT-IMPL)。
- **CIP-6** — 幽靈 entitlement `bank.transfer→econ.transfer`(單處)。
- **CIP-17** — spec 是**部署前 MPT 草稿**,全 5 條 LIVE-DRIFT:§5.2 proof schema 重寫為部署的 QMDB/MMR `SerializableStateProof`+`encoded_operation`;補互斥 `exclusion_proof`(span/empty);`state_root`=全域統一 QMDB root(無 per-actor trie);§5.3 verification 重寫為 MMR op-proof;§5.4 error + §9 rate-limit 更正;清除全部 MPT/「storage trie」引用(CIP-4 是 QMDB)。**light-client fork-class 最高值**。
- **CIP-20** — batch 拒 hooked token(TokenBatchHookedUnsupported);pre-hook vs post-hook gas-cap revert 語義;`MAX_TOKEN_SUPPLY=1e30 wei` 協議上限;body `u256→u128` 全掃(除歷史 Warning 塊)。
- **CIP-29** — unsubscribe/force refund 是 Phase-1 accounting-only(status 註,不刪 intended-economics 表);EventSub/Index key 是 keccak+zero-pad 到 54-byte StateKey(非 raw 33B);§6.3 P1-A/P1-B/P2-D 標 resolved-and-implemented;修陳舊行號註。**0x18/0x19 prefix + 0x12/0x13 quota 已對=STALE-AUDIT 不動**。

**A2 — spec-internal 矛盾(不依賴代碼):**
- **CIP-14** — Part I 註冊費拆分**加總 120%**→burn 前先減 gateway_pool_share(10/20/70)。⚠️ flag:衍生 burn 權重 + 部署的 registry settlement 實為兩方(treasury+burn,無 gateway pool)須 owner/治理定。
- **CIP-19** — §9 廣告 listChanged:true 但 §4/§8 延後 server-initiated→改 false+延後註。
- **CIP-25** — §1.6 finality 述詞寫反(→`H ≤ finalized_height`);`GET /chain/finality` 不存在(NOT-IMPL,交 backend);dead ref `Delta 9 §16.z`→WP §16.2;補 §1.6/App-B revocation-set 檢查(isRevoked)+ L2-Deployment-Isolation 綁定(dst_mailbox 欄 + address(this) 檢查)到 CrossChainMessage/deliver()。
- **CIP-21** — V3 hook「same as V2」軟化(V3-specific 簽名);`schedule_timer(interval=,handler=)`/`trigger_type="state"` 不存在→真 one-shot height API + illustrative-pattern banner。
- **CIP-22** — `_remaining_demand` 最終塊 div-by-zero(`+1`);`_finalize_auction` idempotency guard(double-finalize);不存在的 timer kwargs→one-shot height + self-re-arm;Factory `get_or_create_*→get_*/create_*`(address-vs-handle flag);zero-slippage LP-seeding 操縱註;「reserves 20% block capacity」→`LANE_TIMER_CYCLES=8,888,890 ≈ 11.1%`。

**教訓**:(1)**CIP-17 整份 pre-impl 草稿**——feature 已 ship(#767 系列)但 spec 從未更新,全條 LIVE-DRIFT,proof wire schema 差最遠(MPT vs QMDB/MMR),light-client fork-class 值最高、務必抽 code struct 整塊換;(2)**A2 spec-internal 矛盾(120% 拆分、div-zero、寫反的述詞、dead ref、不存在的 API)不需 code 在鏈上即可修**——與「未上鏈就別碰」的 drift/安全先例不同,是文檔自身缺陷;(3)**not-on-chain 的 illustrative pseudocode(CIP-21/22)**:concrete bug(div-zero/double-finalize/factual 數字)照修,但不存在的 timer API 用 correction banner 而非注入大段未測試 rewrite(surgical,別 over-author);(4)多處 ⚠️ FLAG(CIP-14 權重、CIP-22 factory 回傳型、CIP-25 §B.2 分支)= 修 arithmetic/引用缺陷但把 economic/interface 決策留 owner。

**交付 cowboy#258**(10 CIP,docs-only,base main)。CIP-7 全 STALE-AUDIT 不動(見 14a)。

### 14c. §4 LOW/INFO 長尾(127 條)+ CIP-7 code bug(2026-07-14,cowboy#259 + node#1028)

清 §4 表 127 條 LOW/INFO。**8 agent 並行**(一 group/CIP),回當前 devnet 抽 ground truth 四分類,**working tree 已含 #257+#258**(batch3 branch octopus-merge 兩者,故編當前版)。已 fixed/STALE 逐條丟棄;DECISION(經濟/密碼值、factory 回傳型、committee-cap 衝突)只標 errata。**CIP-10 迴避令排除**。

**涵蓋 23 CIP + 3 WP**(擇要,LIVE-DRIFT 除非註明):
- **CIP-2/3/13/34**:NonReveal key 慣例(單 JSON blob)、slash 單位 `_cby→_wei`、JAIL_EXIT_FLOOR 靜態(非動態 median)、lane-mult floor(mult=0 DoS)、**VRF weight=linear stake×√reputation 非 log2**(真 drift 在 CIP-13 非 CIP-2)、delegation lifecycle events(cip13.* namespace,settlement events 延後)、SubmitSealedBid check order+E1749-1752、EIP-712-"style" 非 wire-format。
- **CIP-14/15/16**:gateway slashing NOT-IMPL、routes rate-limit NOT-IMPL、§6.5→§6.8、AMEND 2-A/2-B 已部署、未記錄 state transitions、SUSPENDED→503、EXTERNAL_REVERIFY_FEE floor。
- **CIP-17/18/19**:`at_block` 已上鏈(height-pinned `/state/at/{height}`)、stale `rpc.rs:168-213`、Runner exposure NOT-IMPL、PaymentBinding 定義、`/_cowboy/mcp`→CIP-18 §17、verb=ANY→POST rationale。
- **CIP-20/21/22**:opcode 表 10-23、刪 stale hook-cap warning、created_at=height、cell-cost 公式、input 約束;TWAP label、Sync-emit、error 表;Requires CIP-1/5、`_get_release_amount` 定義、BlockCleared+currency_raised、can_claim anti-trap、example duration。
- **CIP-23/26/27/28/29**:nonce-beacon producer-side MUST(chain 不可驗)、OperatorRootRef wire、CIP-26 error 表+§2.4→§2.2.4+ASCII names、fee_payer_override de-pin、EMIT_SAME_TOPIC_REENTRY hardcoded、SUBSCRIPTION_CELL_COST_HINT、zombie-reap no-refund;CIP-27 sealed-storage=#236 不動。
- **CIP-4/5/6/31/33**:proof rate-limit、`_payload` raw-JSON 非 base64、timer opcodes 48/49/50、`--no-init` front-run、checkpoint=production、STORAGE_GRACE_EPOCHS=1 epoch、griefing 1/6、TradingPost 0x1E、CIP-13 depends-on、Paused-renew。
- **CIP-7/8/9/12**:SealRequestExpired 欄、Settle 嚴格 `>`、escrow=balance account、chainId=1 caveat、event wire pin、CapToken reserved 欄、Foundation charter 澄清。
- **CIP-25+WP**:nonce/replay scope 統一 `(src,sender,dst,nonce)`、RECLAIM_GRACE "mirrors" 軟化;timer lane ~11%(非 20%)、SemanticSimilarity trust row、relay-handshake domain tag `cbfs:relay-handshake:`、committee-cap 15-vs-16 衝突 flag。

**CIP-7 code bug(附帶,node#1028)**:`cli/actors/stream_actor.py:30` SKM addr `0x12→0x0D`(canonical `ras/src/system_actors.rs`)。範例的兩個 call_actor fallback 打錯 actor;權威 host-fn 路徑不受影響。example-only。

**教訓**:(1)**batch3 stacked on #257+#258**:§4 跨兩 PR 已改的檔,octopus-merge 兩 branch 進 batch3 才編當前版,PR 標 stacked、待兩者 merge 後 rebase 成 §4-only(同 #252→#247 手法);(2)**STALE-AUDIT 佔比極高**:127 條裡大量已被 #248/#252/#257/#258 修或本就正確(CIP-4 20-byte、CIP-5 remove-before-exec、多數 WP 常量)——長尾務必回一手源+讀當前 spec 自檢 done,別重工;(3)**真 drift 常在鄰居 CIP**:C13 log2 那條 audit 掛在 CIP-2,實際 CIP-2 早正確、drift 在 CIP-13;核 drift 要順藤摸到真正 stale 的那份;(4)並行 8 agent 抽全 §4 一趟最省,但 apply 是瓶頸(逐條回源核 verbatim 字串);機械字串用 python sweep,多行 insert 用 Edit。

**交付 cowboy#259**(32 檔 docs-only,base main,stacked)+ **node#1028**(CIP-7 code)。**§4 主體清完**;殘留極少數(changelog 歷史條目、secrets-WP §1.8 domain-separator 8 條需再核、bond-framing errata)價值最低,交團隊 spec-cleanup。
