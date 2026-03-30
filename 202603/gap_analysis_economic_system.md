> [!WARNING]
> **部分内容已过时 (Partially Outdated)**
> 本报告基于 2026-03 初的代码状态，以下条目已于后续开发中实现，**不再是 gap**：
>
> - **CIP-3 EIP-1559 Basefee Engine**（§1 所称"completely missing"）：已于 H-2/M-C 阶段完整实现。
>   相关文件：`node/execution/src/basefee.rs`、`node/execution/src/execution/engine.rs`、
>   `node/storage/src/process_block.rs`。实现包括双轨 basefee 持久化、区块 burn/tip 拆分、
>   `BLOCK_CYCLES_TARGET=10_000_000`、`BLOCK_CELLS_TARGET=500_000`。
>
> §2（CIP-7 Retention Contracts）、§4（CIP-21 DEX）、§5（CIP-22 CCA）、§6（Runner Metering）
> 描述的 gap 截至 2026-03-30 仍未实现，内容依然有效。

# Cowboy Docs vs Code: Economic System Gap Analysis

This report outlines the discrepancies between the authorized technical designs (Whitepaper, CIPs) and the actual implementation in the `node` and `runner` repositories. The focus is specifically on the Cowboy Economic System and related primitives.

---

## 1. CIP-3: Dual-Metered Fee Model

**Status: Partially Implemented (Missing dynamic fee market)**

- **Implemented**: The transaction structure (`node/types/src/execution.rs`) successfully supports the dual-metered design: it includes `cycles_limit`, `cells_limit`, `max_fee_per_cycle`, and `max_fee_per_cell`.
- **GAP - No EIP-1559 Basefee Engine**: The dynamic basefee adjustment mechanism (negative feedback loop adjusting `basefee_cycle` and `basefee_cell` based on block target usage) is **completely missing** from the consensus and memory pool logic. There is no concept of a protocol-level burned "basefee" versus a proposer "tip".
- **GAP - Strict Deterministic Metering Enhancements**: While basic metering exists, it is unclear if the strict determinism enhancements (e.g., dynamic typing surcharges, floating-point software determinism, module whitelist specific costs) outlined in section 2.2.3 of CIP-3 are thoroughly enforced in the PVM.

## 2. CIP-7: Retention Contracts (SLA-Backed Storage)

**Status: Not Implemented**

- **GAP - Total Absence**: The entire mechanism for off-chain data availability is missing. There is no implementation of `RetentionPolicy`, `RetentionContract`, `BlobRef`, or `FeedUpdateEnvelope`.
- **GAP - Watchtower Auditing**: There is zero code for Watchtower attestation logic (`AvailabilityAttestation`), sampling (RANGE vs CHUNK_INDEX), or the penalty/slashing mechanisms for missed retentions.

## 3. CIP-20: Fungible Tokens

**Status: Implemented**

- **Implemented**: The platform-native token primitives are well integrated. `TokenCreate`, `TokenMint`, `TokenTransfer`, `TokenTransferFrom`, `TokenApprove`, `TokenFreeze`, and `TokenSetHook` are fully present in the `SystemInstruction` enums and handled correctly within the `node/chain/src/token` modules.

## 4. CIP-21: DEX & Liquidity Pools

**Status: Not Implemented**

- **GAP - Platform Math Primitives**: The standard math helpers described in the hybrid model (`amm_get_amount_out`, tick math for V3) do not exist as platform primitives. 
- **GAP - Standard Pool Implementations**: There is no code for the standard `V2Pool` (Constant Product) or `V3Pool` (Concentrated Liquidity), nor are there factory contracts to deploy them.
- **GAP - Platform Routing**: The efficient multi-hop routing functions (`amm_swap_exact_in`, `amm_swap_exact_out`) are missing. DEX operations cannot currently be natively routed.

## 5. CIP-22: Continuous Clearing Auctions (CCAs)

**Status: Not Implemented**

- **GAP - Total Absence**: The fair token launch mechanism via Continuous Clearing Auctions is absent. There is no `ContinuousClearingAuction` actor, `AuctionConfig`, or logic to release tokens on a per-block schedule.
- **GAP - Liquidity Seeding**: The atomic functionality designed to graduate a CCA directly into a V2 or V3 liquidity pool relies on CIP-21, which is also unimplemented.

## 6. Off-Chain Market Economics (Runners)

**Status: Partially Implemented**

- **Implemented**: Properties such as `tee_required` are present in the runner job dispatching specs (`runner-common` and `job-dispatcher`), indicating that the off-chain market correctly acknowledges hardware requirements.
- **GAP - Advanced Runner Metering**: The whitepaper emphasizes Runners using extensive *post-mortem metering* (container cgroups, peak memory usage, data transfer). While basic runner infrastructure exists, advanced economic resource accounting (to calculate profit/loss per job dynamically) appears rudimentary or missing in the open-source `runner` code.

---

### Conclusion

The foundational systems required to represent value (CIP-20 Fungible Tokens) and basic dual metering limits are in place. However, the sophisticated **market dynamics** (dynamic basefees, AMMs, fair launch auctions, and retention contracts) laid out in the whitepaper and later CIPs are significant gaps that have not yet been translated into code.
