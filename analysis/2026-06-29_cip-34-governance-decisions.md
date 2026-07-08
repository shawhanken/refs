# CIP-34 Governance Decisions (2026-06-29)

Decision record for the **governance bundle** that unblocks CIP-34 implementation.
Authored under the 2026-06-29 mandate that governance + cross-team work may be
initiated by us. Delivered as cowboy PR amending WP §9.1 + CIP-34 (both on `main`
after #195 merged at `72e0fc4`).

## D-G1 — System-actor address: `0x14` → `INTENT_SETTLEMENT`

**Decision:** Allocate `0x14` to `INTENT_SETTLEMENT` (CIP-34). Reassign the deferred
`EventListener` bridge oracle (WP §16.3) from `0x14` to `0x15`.

**Context:** WP §9.1 dense band has `0x10`–`0x13` taken; `0x1D`/`0x1E` sit outside the
dense band. Rule §9.1.3 says next-free = `0x14`. Both CIP-34's `INTENT_SETTLEMENT`
and the deferred `EventListener` penciled `0x14`.

**Rationale:** `EventListener` is explicitly **deferred** (no implementation, no
timeline); CIP-34 is an **actively-implemented** Core CIP with v0 on the critical
path. A deferred actor yields the dense slot to a spec that is actually landing.
The WP table is amended in the same change (satisfies rule §9.1.3 "update the table
in the same change"). If reviewers prefer the strict rule-§9.1.2 reading (incumbent
WP pencil keeps `0x14`), it is a one-line swap (`INTENT_SETTLEMENT=0x15`,
`EventListener=0x14`) — functionally equivalent; both are free dense slots.

## D-G2 — System-instruction opcodes: reserve `146`–`151`

**Decision:** Reserve the contiguous block `146`–`151` for the six `Intent*`
instructions: `IntentDeposit=146`, `IntentWithdraw=147`, `IntentSettle=148`,
`IntentBroadcast=149`, `IntentRequestWithdraw=150`, `IntentCreditDeposit=151`.

**Context:** `cowboy-protocol-codec`'s `SystemInstruction::sub_type()` (codec rev
`c36a17b`) uses opcodes up to max **145** (banded: 0–23, 30–35, 40–57, 60–63,
68–117, 119–145; gaps at 24–29, 36–39, 58–59, 64–67, 118). There is **no central
WP §9.2 opcode table** — opcodes live in the enum + uniqueness test.

**Rationale:** A contiguous block above the current max avoids the gap-filling
collision class (cf. CIP-12/CIP-16 opcode collisions). Re-pinned at implementation
time against the then-current max by the opcode-uniqueness test (the codec may have
advanced since `c36a17b`).

## D-G3 — Parameter defaults

| Parameter | Value | Basis |
|---|---|---|
| `MAX_SETTLE_INTENTS` | 64 | Initial; MUST be re-validated at impl against measured per-bundle cycles so worst-case ≤ 25% of `LANE_SYSTEM_CYCLES` (≤ 10M of 40M) — so one `settle` can't starve other system instructions in the block. |
| `MAX_DIFFS_PER_INTENT` | 16 | → ≤ 1024 token-diffs/bundle with the above. |
| `GC_GRACE` | 256 blocks | Margin past `deadline` before GC'ing a consumed `(signer,nonce)`; ≥ `DISPUTE_WINDOW_BLOCKS=75`; covers finality lag. |
| `AUCTION_GRACE` | 50 blocks | Sealed-auction key-release liveness fallback (spec default kept). |
| `RECLAIM_GRACE` | 256 blocks | ≥ destination-chain finality buffer before escrow reclaim. |
| `WITHDRAW_TTL` | 86_400 blocks | ≈ 24h at 1 s/block; matches CIP-25 asset-bridge TTL. |
| inbound caps | per-corridor | No global default — set per corridor/backend/asset at enablement; START conservative; pause/kill switch **mandatory**. |
| `SETTLEMENT_DOMAIN_VERSION` | 1 | Fixed `u16`; bumps only on a consensus-critical interface/invariant change. |

All are **consensus-affecting** (change which bundles succeed → `receipt_root`),
so any later tuning is a coordinated **flag-day**.

## Status / follow-on

- These are docs/WP changes; the code (the `0x14` constant, the opcode block, the
  param constants) lands in `cowboy-protocol-codec` + node at implementation M1/M2.
- The two long-pole cross-team items are tracked separately and started in parallel:
  **CIP-24 v1 amendment** (arbitrary-identity + height-triggered release for sealed
  mode) and the **CIP-25 readiness gap-audit** (gates v2 cross-chain).
