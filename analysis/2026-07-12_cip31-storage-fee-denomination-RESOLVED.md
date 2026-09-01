# Resolution note — CIP-31 storage-fee denomination (per-MiB vs per-byte)

**Issue:** cowboyinc/cowboy#237 (audit HIGH H-10) · **Status:** **RESOLVED — recommend close.** · **Class:** was "economic decision + spec/code sync"; investigation shows it is already reconciled.

## What the audit found (2026-07-09)

CIP-31 §1 (redenominated in #231) defines `STORAGE_FEE_PER_MIB_PER_EPOCH = 450` nano-CBY **per MiB**, but the code then in view charged **per byte** (`STORAGE_FEE_PER_BYTE_PER_EPOCH = 10`) — converting to ~10,485,760 nano-CBY/MiB, a ~**23,301×** gap. The audit correctly flagged this as spec-ahead-of-code and routed it to a decision because closing a 4-orders-of-magnitude gap needs an economics sign-off on the target `$/GiB/yr`.

**Important:** that finding was captured against a stale base (`feat/cip34-chat-demo-live`). On current `devnet` the code has since migrated.

## Current state on `devnet` (verified 2026-07-12)

The code now bills **per MiB at exactly the spec value**:

- `cowboy-protocol-types` (`params.rs`, pinned rev `0aa46e1` in `node/ras/Cargo.toml`): `pub const STORAGE_FEE_PER_MIB_PER_EPOCH: u128 = 450;` — **matches CIP-31 §1 (450)**.
- Billing formula: `mib_ceil(effective_size_bytes) * STORAGE_FEE_PER_MIB_PER_EPOCH` — **matches CIP-31 §1** (`ceil(bytes / 2^20)` MiB × rate).
- `node/ras/src/lib.rs:52`: `pub const TRANSFER_FEE_PER_MIB: u128 = 10_000;` — **matches CIP-31 §2 (10,000)**.
- The old per-byte constants (`STORAGE_FEE_PER_BYTE_PER_EPOCH`, `TRANSFER_FEE_PER_BYTE`) are **gone** from the codebase (grep: zero hits).
- `node/ras/src/lib.rs` re-exports the per-MiB constant; `execution/`, `storage/`, `chain/genesis.rs`, `rpc/` all consume `STORAGE_FEE_PER_MIB_PER_EPOCH` / `rent_rate_per_mib_epoch`.

Both the storage-rate and the transfer-rate denomination mismatches the audit raised are closed: **code == CIP-31 §1/§2**, per MiB, at 450 / 10,000 nano-CBY.

## Recommendation

**Close #237 as resolved.** No economics decision remains — the code adopted the #231 per-MiB redenomination and the values are byte-for-byte the spec's. The `$/GiB/yr` target the audit worried about is the one CIP-31 §1 already documents (~$0.17/GiB/yr at CBY=$1). If economics still wants to *re-tune* the absolute rate, that is ordinary Tier-0 governance (key `system:cbfs:storage_fee_per_mib_per_epoch`), not an audit finding.

One optional tidy-up (not blocking): confirm the pinned `cowboy-protocol` rev used by the release matches the one carrying `= 450`, so a future rev bump can't silently regress the value; a genesis/param assertion test on `STORAGE_FEE_PER_MIB_PER_EPOCH == 450` would lock it.

---
*Generated as an audit follow-up verification (2026-07-12). Advisory only.*
