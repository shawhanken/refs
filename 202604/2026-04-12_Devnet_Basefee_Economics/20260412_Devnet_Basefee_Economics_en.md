# On-Chain Basefee Economics (Devnet Version): Evolution and Comparison

**Document date:** 2026-04-12  
**Scope:** Consensus parameters and implementation of the Cowboy **`devnet` version** (development / test-network deployment—not a mainnet commitment).  

---

## 1. Executive summary

The Cowboy **devnet version** implements **CIP-3-style dual metering (Cycles / Cells)** and **two independent EIP-1559-style basefee tracks**: compute and data are priced separately, and each track adjusts algorithmically from block to block based on usage versus a protocol target.  

Across **devnet version** iterations, the **core pricing formula has remained stable**. What changed is mainly: **per-block cycle budgets and lane splits**; **EIP-1559 targets** \(T_c\): **per-block compute** (cycles), \(T_b\): **per-block data** (cells; 1 cell = 1 byte); **genesis basefee levels**; **whether failed transactions pay fees**; **where tips accrue**; and **which account pays gas (sender vs actor / owner)**.  

The **current devnet version** **intentionally or incidentally diverges** from some numbers stated in CIP-3 (e.g. lane table, \(T_c = 10\text{M}\) compute target), prioritizing **throughput benchmarking and operational stability**. A dedicated pass is needed to **reconcile on-chain constants with published specs** before any mainnet-style commitment.  

---

## 2. Evolution timeline (devnet version)

Phases are logical groupings derived from the **devnet version** implementation history; boundaries are not strict release milestones.

| Phase | Theme | Highlights |
|-------|--------|------------|
| **A** | Dual metering + dual basefee | Introduces `cycle_basefee` / `cell_basefee` with independent EIP-1559 updates; early `BLOCK_CYCLES_TARGET = 5M`, `BLOCK_CELLS_TARGET = 500k`; initial cycle/cell basefees were temporarily asymmetric (e.g. cycle 1e9, cell 1e8); `ALPHA = 8` (~±12.5% max change per block). |
| **B** | Whitepaper alignment + block lifecycle | Targets move to **10M cycles / 500k cells**; **0x06** fixed as DualBasefee system actor; `process_block` and `ExecutionEngine` load state, accumulate usage during execution, update from parent usage, and persist; speculative batch execution model matures. |
| **C** | Security audit: incentives & abuse | **Failed transactions still pay fees and advance nonce**; **basefee component burned to zero address**; **tips paid to the block proposer** (address derived from leader key), fixing broken proposer incentives; more settlement logic consolidated at the speculative layer. |
| **D** | Payer model: actor-pays | **Gas debited from the actor first**; optional **`UseOwnerBalance` entitlement** falls back to owner, then sender; **`FundActor`** and related flows fund on-chain accounts. This does **not** change the basefee/tip formulas—only **who pays**. |
| **E** | Throughput: lane expansion & retuning | System lane raised (e.g. **5M → 25M**); **`BLOCK_CYCLES_TARGET` and total lane caps** retuned so a **single saturated lane** can drive the per-block adjustment cap; in the **current devnet version**: **\(T_c \approx 12.5\text{M}\)** (per-block compute target), **\(T_b \approx 2.5\text{M}\)** (per-block data target), **50M** total across four lanes. |
| **F** | Observability | Benchmarks and metrics add stronger basefee tracking for load testing and tuning.  

---

## 3. Capability shifts (benefits vs trade-offs)

| Change | Benefit | Cost, risk, or spec tension |
|--------|---------|------------------------------|
| Dual basefee | **Separate markets** for compute vs data | Wallets must handle **two dimensions** of max fee and tip |
| Target & lane retuning | Basefee tracks **real per-block bottlenecks** and product TPS goals | Easy **drift from CIP-3 tables**; docs or constants must be updated deliberately |
| Initial fees: asymmetric → symmetric, lower | **Cheaper, symmetric** testnet for experimentation | Mainnet genesis would need a **fresh economic review** |
| Failed-tx fees + tips to proposer | **Spam resistance** and **correct proposer incentives** | Users **pay on failure**; product copy should say so clearly |
| Settlement in speculative layer | Block-level burn/tip/basefee consistent with **batch execution / verification** | Cross-cutting **execution + storage** complexity for debugging |
| Actor-pays + owner fallback | Apps can **sponsor gas** | Larger **authorization and balance** audit surface |
| `ALPHA = 8` with ~1s blocks | Matches common doc-style parameter | Versus Ethereum’s ~12s blocks, **adjustment per real time can feel faster** |
| Basefee **floor on downward updates** (`MIN_BASEFEE`) | Caps how low the EIP-1559-style adjustment can fall—**distinct from** genesis / default starting prices (`INITIAL_*_BASEFEE`) | The **numeric floor is version- and deployment-specific**; for external communication, cite **on-chain state or release notes**, not a historical test constant |

---

## 4. Past / present / target direction

**Past** summarizes the early **devnet version** (first dual-basefee landing through whitepaper-aligned targets). **Present** reflects the **current devnet version** (`types/src/constants.rs`, etc.). **Target direction** captures **intended priorities** for economics and protocol evolution, to align expectations with stakeholders—it is **not** a fixed schedule or delivery commitment.

| Dimension | Past (early devnet version) | Present (current devnet version) | Target direction |
|-----------|---------------------|--------------------------|------------------------------|
| Dual basefee | Present | Unchanged | **Retain**; reconcile constants or revise docs |
| EIP-1559 responsiveness | `ALPHA = 8` (~±12.5%/block) | Still 8 | **Possible** larger α for 1s cadence; **not** changed in the **devnet version** yet |
| \(T_c\) (per-block compute target, cycles) | 5M → later 10M | **12.5M** | **Continue retuning** \(T_c\) for throughput |
| \(T_b\) (per-block data target, cells) | 500k | **2.5M** | **Keep** \(T_b\) **scaled with** \(T_c\) |
| Total lane budget | Smaller system lane → expanded | **50M** total, system **25M** | **Performance-first**; static spec tables go stale quickly |
| Initial basefees | Asymmetric (e.g. 1e9 / 1e8) | **1e8** both | Testnet-friendly; **revisit for mainnet** |
| Basefee burn | By design | **To `Address::ZERO`** | **Keep** deflationary narrative |
| Tip recipient | Implementation risk period | **Current block proposer** | **Lock in** incentives |
| Failed-tx fees | Free-failure window existed | **Failures pay** | **Tighten** free paths further |
| Debited account | Mostly sender | **Actor → entitled owner → sender** | **App-sponsored** gas more common |
| Settlement locus | More per-tx | **Speculative block aggregate** | **Keep** block-level model |
| vs CIP-3 | Already drifted from first constants | **Still partially divergent** | **Either on-chain or spec must move** |

