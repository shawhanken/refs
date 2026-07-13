# System-Actor Address Reconciliation — `0x11` / `0x13` collision (deep-audit §6)

_2026-07-13. Resolves the one **real** cross-spec collision surfaced by the deep-audit §6 collision scan, run the cheap way (deterministic diff against the source-of-truth registry, **no verification agents** — per the §6 recommendation). Companion to `2026-07-09-cips-wp-deep-audit.md`._

## 1. Method (reproducible / CI-able)

The on-chain source of truth for system-actor addresses is `node/runner/src/system_actors.rs` (the `SystemActorAddresses` enum); for opcodes it is `cowboy-protocol/crates/cowboy-protocol-codec/src/instruction.rs` (`SYS_*` constants, guarded by `#[deny(unreachable_patterns)]` on `Read for Instruction`). Extraction + diff:

```bash
# canonical opcode table (name -> value); source-of-truth has NO duplicate values
grep -oP 'pub const SYS_[A-Z0-9_]+: u8 = [0-9]+' \
  cowboy-protocol/crates/cowboy-protocol-codec/src/instruction.rs \
  | sed -E 's/pub const (SYS_[A-Z0-9_]+): u8 = ([0-9]+)/\2 \1/' | sort -n
# -> 143 opcodes, range 0..159, zero collisions

# canonical system-actor addresses (hex -> name)
grep -oP '\b[A-Z][A-Z0-9_]+ = 0x[0-9A-Fa-f]+' node/runner/src/system_actors.rs
# -> 21 addresses, zero collisions
```

The full reconciliation checker (`refs/analysis/check_alloc.py`) scans every `cowboy/docs/cips/*.md` for opcode/address numeric claims and diffs against the canonical maps. **This is the CI seed the audit §6 asked for** — wire it as a check that fails on any spec claim diverging from `system_actors.rs` / `instruction.rs`.

## 2. Finding — the WP §9.1 "canonical" table conflicts with deployed code on `0x11`/`0x13`

| addr | WP §9.1 table (pre-fix) + CIP-10/14/16/18/34 | Deployed registry (`system_actors.rs`) | Status in code |
|------|----------------------------------------------|----------------------------------------|----------------|
| `0x11` | **Container Registry** | **`VALIDATOR_SET`** (CIP-11) | **code-deployed** — allocated at genesis with `ValidatorRecord`s (`node/chain/src/genesis.rs`), read via `node/execution/src/validator_set.rs` |
| `0x12` | PaymentGate | *(unallocated; PaymentGate reserved)* | spec-allocated / unbuilt |
| `0x13` | **BankActor** (CIP-28) | **`CONTAINER_REGISTRY`** (CIP-10) | **code-deployed** — Council-pausable (`node/types/src/pause.rs`, `runner/verifier.rs:1115`), compute-fee escrow |
| — | *(VALIDATOR_SET absent from table)* | `VALIDATOR_SET = 0x11` | code-deployed |

Root cause: the deployed registry placed the CIP-11 validator-set snapshot at `0x11` and, per its own enum comment (*"0x11 was taken by the CIP-11 validator-set snapshot and 0x12 is spec-allocated to the CIP-18 PaymentGate, so the registry sits at the next free slot"*), put the Container Registry at `0x13`. The specs never caught up: the WP §9.1 table (which cip-10:1059 itself calls *"the canonical cross-CIP allocation table"*) still shows Container at `0x11`, omits `VALIDATOR_SET` entirely, and lists an unbuilt `BankActor` at `0x13` — **colliding with the deployed Container Registry**.

Impact: an independent client built from any of these specs would place the Container Registry at `0x11` (colliding with the deployed validator-set actor) and would not know `0x11` is the validator-set snapshot. This is the audit's core "spec-only client forks" thesis, in an address that is genuinely deployed.

Direction is **not** a governance choice: `VALIDATOR_SET @ 0x11` is a genesis-allocated identity anchor (moving it is a flag-day genesis change) and `CONTAINER_REGISTRY @ 0x13` is deployed + pausable. Per the WP §9.1 notes 1–2 (*"the implementation registry is the source of truth… this table MUST track it"* and *"a deployed claim wins"*), **the specs must be corrected to code.**

## 3. Disposition

### Fixed in this pass (cowboy PR — see below)
- **WP §9.1 table** (anchor): `0x11` → Validator Set (CIP-11, code-deployed) with errata; `0x13` → Container Registry (CIP-10, code-deployed) with errata; dense-band phrasing `0x01–0x13` → `0x01–0x14`; a reconciliation callout after the allocation-rule notes. The unbuilt **BankActor** row is flagged as colliding and **must relocate** (see decision below).
- **CIP-14** (§ address table), **CIP-16** (§ address table), **CIP-18** (§ address table + v2-sequence prose), **CIP-34** (§ WP-9.1 reference): Container `0x11` → `0x13`, `0x11` row added/relabeled as `VALIDATOR_SET`.

### Left for the CIP-10 owner (not edited — CIP-10 out of scope for this actor)
`cip-10-runner-containers.md` states Container Registry at `0x11` in **7 places** (frontmatter `description`, header §1 title, §1 body :1059, tables :1070/:1095/:1107, and the intro callout :14). These are the Container Registry's **own** CIP and must be corrected to `0x13` by its owner. Flagged in the WP §9.1 reconciliation callout. **This is the only remaining `Container=0x11` holdout after this pass** (verified by grep).

### Decision (not arbitrated) — BankActor (CIP-28) address
BankActor was penciled at `0x13`, now occupied by the deployed Container Registry. BankActor (CIP-28 agent-banking) is **unbuilt on-chain**. It MUST take a next-free address per the §9.1.3 rule. Candidate next-free slots (occupied: `0x01`–`0x11`, `0x13`, `0x14`, `0x1D`, `0x1E`; reserved: `0x12` PaymentGate; penciled: `0x15` deferred EventListener per CIP-34): **`0x15` or `0x16`**. Recommendation: assign BankActor `0x16` (leaving `0x15` for the already-penciled EventListener) — but the exact slot is a **CIP-28 / governance decision**, not made here. When CIP-28 is drafted for implementation, it MUST bind its slot in the WP §9.1 table in the same change.

## 4. Everything else the scan flagged = benign / already-known (no action)
- **Opcode source-of-truth: zero duplicate values** (143 constants, compile-time-guarded). The 130 §6 "collision candidates" are per-CIP local enumeration reuse (e.g. `0x01`–`0x05` reused across many local instruction enums) — benign, confirmed by the human read in §6.
- `SYS_VALIDATOR_*` (CIP-11:66/72) and `SYS_SESSION_*` (CIP-8:438) references are **correct prose** — CIP-11 explicitly says the `SYS_VALIDATOR_*` instruction does *not* exist; CIP-8 correctly notes `SYS_SESSION_*` must be added to the uniqueness test. Not drift.
- `SYS_FETCH_SECRET_METADATA` (CIP-24:1186) is a runner **host syscall** in pseudocode, not a wire `SystemInstruction` opcode — legitimately absent from `instruction.rs`.
- The two previously-known real collisions (dual `cip-15-*` files; CIP-10 opcode `61–64` vs `160–164`) are already recorded in the audit §2/§3 and are separate from this address finding.
