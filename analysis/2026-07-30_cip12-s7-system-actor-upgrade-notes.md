# CIP-12 §7 (System-Actor Upgrade) — two notes for the spec owner

_2026-07-30. Surfaced during a governance-proposal validation-consistency audit of the node
(`execution/src/execution/system_instruction.rs` + `execution/src/execution/gov_enact.rs`). Both items
are advisory — neither is an exploitable bug in the current codebase._

## 1. Prerequisite: an on-chain `new_code_hash`-resolvability guard must land **before** the dispatcher code-swap is wired

**Current state (no bug today).** The on-chain upgrade path (`SubmitUpgradeSystemActorProposal` →
`ProposalPayloadKind::UpgradeSystemActor` → `apply_upgrade_system_actor`) writes an `ActorVersionRecord
{ code_hash, activated_at_block, rollback_deadline_block }` but **nothing consumes it**: no dispatch or
activation path reads `version_key_for` / `activated_at_block` outside the enactment itself and tests, and
the pausable system actors (0x01–0x1E) execute native Rust handlers via the `SystemInstruction` match — not
bytecode loaded by the record's `code_hash`. This matches the spec's own on-chain-status note
(`cip-12-governance.md:315`): the `code_ref`, fetch, and dispatcher code-swap are "part of the intended
design but are **not yet on-chain** … enactment only writes the `code_hash`/rollback pointer." So a
`new_code_hash` that references no deployed bytecode is harmless today — it is written into an unconsumed
record.

**The gap that opens when the swap is wired.** The spec requires resolvability at submission — §7.2.2
(`:322`): "`code_ref` resolves to bytecode whose hash matches `new_code_hash`." But that check is
**spec-only**: the on-chain struct has no `code_ref` (`:315`), and neither the submission handler
(validates only tier / voting-window / `is_pausable_actor` / rollback-window) nor enactment
(`apply_upgrade_system_actor`) verifies the hash resolves to deployed bytecode. Separately, §7.4 (`:337`)
describes a missing-code node only as a per-validator liveness lag ("fails to execute messages to `target`
until it catches up"), **not** a chain-level guard.

If the dispatcher code-swap is wired against the same content-addressed loader used elsewhere
(`store.get_code(code_hash)`, which returns `.unwrap_or_default()` → **empty code** on a miss,
`pvm_host.rs:1069`), then a passed upgrade proposal to an unresolvable hash would silently swap the target
system actor to empty code — a governance-gated brick (recoverable via the §7.5 rollback slot, but a brick
nonetheless). **Recommendation:** make the §7.2.2 resolvability check a normative on-chain gate (at
submission and/or as a pre-activation validity check), and treat it as a hard prerequisite of the
code-swap work — i.e. land the guard in the same change that wires the swap, never after.

_(Note: adding a `get_code(new_code_hash).is_some()` check to the node **now** would be premature and
possibly wrong — the spec stages bytecode in **CBFS** (`code_ref: CbfsRef`, `:296`), not the on-chain PVM
code store, so the correct resolvability target should be settled as part of wiring the swap.)_

## 2. Spec internal inconsistency: `0x1D` is in the §7.2.1 upgradeable allowlist but is excluded from bytecode swap by §7 line 129

- §7.2.1 pausable/upgradeable allowlist (`:321`) includes `0x1D`.
- §7 Tier table (`:129`) states virtual / intercepted actors such as `0x1D` (CIP-29) are "upgraded via
  **protocol-level code changes, not bytecode swap**."

So `0x1D` is simultaneously listed as a bytecode-swap-upgradeable target and declared not-bytecode-swappable.
**Recommendation:** either remove `0x1D` from the §7.2.1 upgradeable allowlist, or add an explicit carve-out
saying virtual actors in the allowlist are pausable-only (not swap targets). Worth reconciling before the
swap path is implemented, so the `is_pausable_actor` set the node enforces and the §7.2.1 list agree on
whether `0x1D` accepts an `UpgradeSystemActor`.

---

_Both items are forward-looking: they matter when the §7 dispatcher code-swap moves from "intended design"
to on-chain. No action is required on the current (inert) implementation._
