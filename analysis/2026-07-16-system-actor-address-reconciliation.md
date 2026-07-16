# Cowboy System Actor Address Reconciliation

**Date:** 2026-07-16
**Scope:** every `.md` in `cowboy/docs/cips/` (cip-1 … cip-34) and `cowboy/docs/whitepaper/`.
**Source of truth:** Whitepaper §9.1 self-declares as the single authoritative registry
(`whitepaper/cowboy-technical-whitepaper.md:794` — every CIP MUST agree; per-CIP tables are
informative mirrors). Addresses are 20-byte low-byte shorthand (`0x09` = `0x00…09`).

> Method note: this document reconciles the **spec text only**. Where a governance decision made
> outside the docs points a different way, that is called out explicitly (see §2) rather than
> silently resolved — the spec text is not automatically the settled answer when a live
> governance decision contradicts it.

---

## 1. Consistent address list (0x01–0x1E)

| Addr | Role | Status | Canonical | Corroborating specs |
|------|------|--------|-----------|---------------------|
| `0x01` | Runner Registry | deployed | wp:798 | cip-16:904, cip-14:1320, cip-23:68, cip-18:974 |
| `0x02` | Job Dispatcher | deployed | wp:799 | cip-16:905, cip-14:1321, cip-23:69, cip-12:294 |
| `0x03` | Result Verifier | deployed | wp:800 | cip-16:906, cip-14:1322, cip-23:70 |
| `0x04` | Secrets Manager (CBSS) | deployed | wp:801 | cip-16:907, cip-14:1323, cip-24:1080-1082 |
| `0x05` | TEE Verifier (state co-located under 0x04) | deployed | wp:802 | cip-16:908, cip-23:72, cip-10:1063 |
| `0x06` | Dual Basefee · Token Registry (co-located, disjoint keys) | deployed | wp:803 | cip-16:909, cip-12:112 |
| `0x07` | Entitlement Registry | deployed | wp:804 | cip-16:910, cip-14:1326 |
| `0x08` | Treasury | deployed | wp:805 | cip-16:911, cip-14:1327 |
| `0x09` | **Governance** (`GOVERNANCE_SYSTEM_ACTOR`) | deployed | wp:806 | cip-12:16/79, cip-3:152, cip-2:228/366, cip-10:15 |
| `0x0A` | Storage Manager | deployed | wp:807 | cip-16:913, cip-9, storage-wp:53/594 |
| `0x0B` | **Relay Registry** | deployed | wp:808 | cip-16:914, cip-14:1330, storage-wp:54/594, cip-31:143 |
| `0x0C` | Session Actor | deployed | wp:809 | cip-16:915, cip-18:975 |
| `0x0D` | Stream Key Manager | deployed | wp:810 | cip-16:916, cip-18:976 |
| `0x0E` | Route Registry | deployed | wp:811 | cip-16:917, cip-18:977 |
| `0x0F` | Gateway Registry | reserved | wp:812 | cip-16:918, cip-18:978 |
| `0x10` | Receipt Registry | reserved | wp:813 | cip-16:919, cip-18:979 |
| `0x11` | Validator Set (CIP-11) | deployed | wp:814 | cip-16:920, cip-18:980, cip-12:16 |
| `0x12` | PaymentGate (CIP-18) | spec-allocated (no handler) | wp:815 | cip-16:921, cip-18:970-982/1006 |
| `0x13` | Container Registry (CIP-10) | deployed | wp:816 | cip-18:982, cip-10:14/1059, cip-12:16 |
| `0x14` | INTENT_SETTLEMENT (CIP-34) | spec-allocated | wp:817 | cip-34:19/196, cip-12:16 |
| `0x15` | EventListener (CIP-29 bridge oracle) | spec-reserved (deferred) | wp:818 | wp:971, cip-34:196 |
| `0x16` | BankActor (CIP-28) | spec-allocated (unbuilt) | wp:819 | cip-28:5/13/29/87/819 |
| `0x1D` | Event Subscription (CIP-29) | virtual (host-intercepted) | wp:820 | cip-29:417-421, cip-12:16 |
| `0x1E` | TradingPost (CIP-33) | deployed (devnet) | wp:821 | cip-33:89, cip-12:16 |

`0x01`–`0x13` are mutually aligned across CIP-14/16/18/10 and wp §9.1. No live cross-doc
contradiction remains in the `0x01`–`0x1E` allocation itself.

---

## 2. LIVE / UNRESOLVED — CIP-31 CBFS params: 0x09 vs 0x0B  ⚠️ needs human decision

`storage_fee_per_mib_per_epoch` is assigned **two different addresses inside the one CIP-31 document**:

- `cip-31-cbfs-rent-schedule.md:39` (§1) — stored at **`0x09`** (Tier-0 governance param).
- `cip-31:143-149` (§10 "Parameter Storage at **0x0B** Relay Registry" + §11 table) — the same
  key is listed among the **`0x0B`** keys, read by Storage Manager `0x0A`.

Every other CBFS parameter in CIP-31 (§2:49, §3:59, §4:68, §7:115-116, §8:137, §10 block, §11
table :167-183) is at `0x0B`. Only §1 line 39 says `0x09`.

**The two candidate resolutions point in OPPOSITE directions — do not auto-fix:**

- **Spec-text weight → 0x0B.** §10/§11 body is unambiguous; wp §9.1 role of `0x0B` is exactly
  "Relay Registry / PoR challenges" (wp:808); the wp §13.1 catalogue of `0x09` governance keys
  (wp:902-960) contains **no** `system:cbfs:` entry; CIP-12 §4.2 (cip-12:112) says structured
  per-actor configs live at their owning actor, not `0x09`. On text alone, §1 line 39 is the
  outlier and would be corrected to `0x0B`.

- **Governance decision → 0x09.** Per the closes of cowboy PRs #267/#268/#269 (2026-07-16,
  shawhanken): CBFS rent **parameters** reconcile to governance actor **`0x09`** under the
  `cip31.cbfs.*` namespace (matching the as-built COW-1163 path); **`0x0B` holds
  escrow/pool/bond state only**. On this reading, §10/§11's parameter-storage wording is what
  needs correcting, not §1 line 39. Those three PRs (which pushed §1's `0x09` → `0x0B`) were
  retracted as unauthorized AND wrong-direction; the correct reconciliation is to be opened
  separately by a human.

**Action:** hold for human ruling on which address owns CBFS **parameters** (vs escrow/pool/bond
state at `0x0B`). Whichever way it lands, CIP-31 must be made internally consistent — right now
§1 and §10/§11 contradict each other regardless of the answer.

---

## 3. Allocation scheme

- `0x0000…0100` reserved for system actors / precompiles (wp:96, :471); actors below
  `RESERVED_SYSTEM_ADDRESS_LIMIT` are rent-exempt (wp:832). User actors cannot land here
  (CREATE2-derived).
- Dense sequence `0x01`–`0x16`, next-free-slot (next is `0x17`; wp:829).
- `0x01`–`0x0F` rejected by PVM for fee_payer overrides / deploy (wp:832, cip-5:145, cip-29:421,
  cip-6:860). `0x01`–`0x10` exempt from "actor does not exist" 404 → return exclusion proofs
  (cip-17:159).
- `0x1D` (virtual Event Subscription) and `0x1E` (TradingPost) sit deliberately outside the
  dense band (wp:820-821, cip-29:417-421, cip-33:89).
- Collision rule (normative, wp:828): deployed claim wins; among undeployed, lowest-numbered
  spec wins, loser renumbers.

There is **no `0x9X` "runner-system" band** anywhere in the specs — the runner system actors are
`0x01`/`0x02`/`0x03`/`0x04`/`0x05` in the low band. (The `0x91`–`0x95` values are node
`constants.rs` implementation addresses, NOT spec addresses; out of scope for this doc.)

---

## 4. Resolved historical collisions (change-log residue only, not live)

- Container Registry `0x11` → `0x13` (deployed-claim-wins; wp:814/816/831; corrected in cowboy#260).
- BankActor `0x0D` → `0x13` → `0x16` (cip-28:5, reassigned 2026-07-14).
- EventListener `0x14` → `0x15` (freed for INTENT_SETTLEMENT; cip-34:196, wp:818/971).
- Event Subscription `0x0A` → `0x1D` (early CIP-29 draft collided with Storage Manager; cip-29:421).
- PaymentGate `0x0013`/`0x11` → `0x12` (cip-18:982/1006).
- Whitepaper `changelog.md:64/66/78` — stale redline narrative, not current assignments.

---

## 5. False-positive namespaces (NOT actor addresses — do not reconcile against the table)

- CIP-4 storage-column prefixes `0x01`–`0x1D` (cip-4:91-119, 336-348) — QMDB key-space column
  tags (e.g. `0x0A` here = SystemState column, unrelated to Storage Manager `0x0A`).
- CIP-7 storage-key prefixes `0xD || 0x0X` (cip-7:183-187, 800-803).
- CIP-11 wire opcodes `0x01`/`0x10`/`0x20` (cip-11:938-944).
- CIP-30 hash domain-separation tags `0x00`/`0x01`/`0x02` (cip-30:74-83).
