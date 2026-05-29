# Whitepaper Changelog

All notable changes to the Cowboy whitepaper documents are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [2026-05-28] - Decouple Whitepaper from CIPs

### Changed

**Technical Whitepaper (`cowboy-technical-whitepaper.md`)**
- Removed all direct CIP-X / CIP-X §Y inline references. The WP is positioned as the foundational reader-facing document; specific CIP citations have been replaced by inlined parameters, rules, or general descriptions, with a forward-looking note that detailed design will be elaborated in future CIPs.
- Removed the version-banner block ("v2.r2", revision history, summary of Part II deltas) and the wrapping "Part I — v1 Whitepaper" heading; the document now reads as a single canonical WP.
- Rewrote **§9 System Actors & Precompiles** to match the canonical low-byte allocation in code (`0x01`–`0x0C`): added Storage Manager (`0x0A`), Relay Registry (`0x0B`), Session Actor (`0x0C`); corrected Secrets Manager description for CBSS; moved Container Image Registry to "from `0x0D` upward as formalized."
- Cleaned `Decision Register #4` / `C7` / "HOLD" audit-residue terminology (§8.4 footnote ², §13 off-chain block, §17.5).
- Removed redline-comment residue ("0x09 is now reserved", "0x08 is currently assigned to Treasury", dangling `_deferred_` parenthetical).
- Fixed broken §-pointer in §3.3 (`§5.1` → `§5.1a`).
- Softened v1/v3 phasing ("v3 once activated") into "v1 / target design" neutral phrasing throughout.

**Secrets Whitepaper (`cowboy-secrets-whitepaper.md`)**
- Same CIP-reference cleanup. References to CIP-2, CIP-9, CIP-12, CIP-13, CIP-23, CIP-24 replaced by neutral phrasings.
- Fixed broken `§0 cryptographic construction` pointer → "the **Cryptographic Construction** section."
- Resolved orphan `Tier-0 / Tier-1` governance and "actor upgrade path" / "TEE Verifier state" references with explicit cross-refs to Technical Whitepaper §3 / §9 / §11.
- Updated `§§1–13` "Normative requirements" claim to `§§1–15` (§14 / §15 also carry normative requirements).

**Storage Whitepaper (`cowboy-storage-whitepaper.md`)**
- Same CIP-reference cleanup. References to CIP-4, CIP-9, CIP-12, CIP-14 replaced by neutral phrasings.
- Fixed the §-On-Chain Control Plane cross-ref (the Storage Manager `0x0A` / Relay Registry `0x0B` allocations now match the canonical Technical Whitepaper §9 table).
- Fixed inconsistent `§State Transition Function` reference style.
- Fixed misdirected `§5` cross-ref for cache-refresh bound; now points to the Cache Freshness section.

**Design Decisions (`cowboy-design-decisions.md`)**
- Resolved three long-standing contradictions against the Technical Whitepaper, in each case bringing the design-decisions narrative in line with the actual implementation:
  - **Scheduler description:** Removed the "Tiered Calendar Queue" three-tier description; it never matched the code, which uses height-indexed FIFO storage. Rewrote the sub-section to describe height-indexed storage + per-fire `fee_payer` model + the future EIP-1559 hybrid (matching `node/storage/src/timers.rs` and Technical Whitepaper §5.1).
  - **Anti-starvation:** Removed the "weighted priority system with exponential decay" claim. Replaced with the per-actor fairness weight `W(actor) ∈ [1, 2]` from the target design.
  - **Bridge framing:** Removed the "canonical bridge" framing; clarified that bridge infrastructure is third-party / governance-selected and that actor access is gated by the `bridge.asset` and `bridge.subscribe_event` entitlements (matching `node/types/src/registry.rs`).
- Added Steamtrain / container batch jobs / MCP tools to the off-chain compute overview to match the technical scope.
- Expanded `MEV` and `VRF` acronyms on first use; clarified `CBY` as the native protocol token.

**Cross-cutting consistency fixes**
- Technical WP §3.6 Key Features bullet for native timers now describes the actual scheduler (height-indexed FIFO + per-fire `fee_payer`); previously described a "tiered calendar queue" that does not exist in code.
- Technical WP §16 introductory framing changed from "canonical bridge" to "governance-selected third-party bridge"; now consistent with §16.2.
- Technical WP MEV "Out of scope" enumeration in the Architectural Overview deduplicated against §6.5; the overview now defers to §6.5 for the full list.
- Secrets WP §3 opcode table extended from 14 entries (68–81) to 17 entries (68–84): added `ExpireLivenessChallenge` (82), `RequestReshare` (83), `ForcedDeregisterCbssProxy` (84) to match `node/types/src/execution.rs`.
- Secrets WP fixed misdirected `§6.2` cross-ref → `§5.3` (request validation).
- Secrets WP removed Unicode soft-hyphen artifacts (`accept​able` → `acceptable`) at §5/§6 boundary lines.

### Removed

**Technical Whitepaper**
- Deleted **Part II — v2 Proposed Deltas (CIP-14/15/16 alignment exercise)** and **Part III — WP-vs-CIP-Aligned Audit Brief**. These were CIP-alignment scratch documents, not WP content. Preserved verbatim in `analysis/2026-05-28_wp-aligned-deltas-v2.md` and `analysis/2026-05-28_wp-alignment-brief-v2.md` for internal reference.

### Rationale

The whitepaper sits above the CIP series in the document hierarchy. Direct citations like "(CIP-5 §6.4)" inside the WP create the reverse dependency — readers cannot understand the WP without already knowing the CIP graph, and the WP rots whenever a referenced CIP is revised. Replacing CIP anchors with inlined content keeps the WP self-contained while leaving detailed normative work to future CIPs.

The §9 system-actor table rewrite resolves a long-standing conflict: the prior WP listed `0x0A = Container Image Registry`, but the actual code allocates `0x0A = Storage Manager` (CBFS implemented first; container registry rolled forward). The Storage Whitepaper was already correct; the Technical Whitepaper now matches.

---

## [2026-04-20] - Atomic Actor Initialization

### Added

**Technical Whitepaper (`cowboy-technical-whitepaper.md`)**
- New **§3.6: Actor deployment and atomic initialization**. Specifies the normative semantics of `init_handler` / `init_payload` in the `DeployActor` transaction: atomic execution within the deploy frame, revert‑propagation from failed init, observational guarantee that no transaction may observe a deployed actor in its pre‑init state, and the SDK default of `init_handler = "init"`. Step 1 of the execution sequence handles the pre‑existence check with an `AddressCollision` revert.
- Extended **§2.1** with the `DeployActor` payload shape (`{ code, salt, manifest?, init_handler?, init_payload? }`), making actor creation a first‑class transaction kind in the spec.

### Rationale

Atomic init is a consensus‑critical property, not a tooling convention: validators agree on whether to invoke the init handler, charge the caller's fee budget for its execution, and propagate revert state if it fails. Omitting it from the whitepaper left an interoperability risk — alternate implementations could have read the spec, ignored the init fields, and still believed they were conformant while forking from the reference implementation.

Ecosystem conventions that are NOT enforced at the protocol level (e.g. dunder‑key actor identity metadata, discussed in `architecture/actor-vm/actor-identity.mdx`) remain outside the whitepaper.

---

## [2026-01-19] - Fee Model Specification

### Added

**Technical Whitepaper (`cowboy-technical-whitepaper.md`)**
- New **§17: Fee Model Specification** consolidating all fee and cost information:
  - 17.1 Overview of dual-metered system (Cycles + Cells)
  - 17.2 Transaction intrinsic costs by type
  - 17.3 Execution costs (Actor API, Platform Tokens)
  - 17.4 On-chain storage costs (Cells)
  - 17.5 State rent formula and eviction rules
  - 17.6 Off-chain blob storage
  - 17.7 Runner marketplace pricing model
  - 17.8 EIP-1559 fee adjustment parameters
  - 17.9 Reserved capacity allocation (execution lanes)
  - 17.10 Fee estimation pseudocode

---

## [2026-01-18] - Expanded "Why a Sovereign L1" Section

### Added

**Design Decisions (`cowboy-design-decisions.md`)**
- New **Execution Model Incompatibilities** subsection explaining why Cowboy's primitives cannot exist on an L2:
  - Scheduled future execution (native timers vs external keepers)
  - Actor-aware block building (anti-starvation, timer priority)
  - Guaranteed execution lanes (reserved capacity per transaction type)
  - Storage lifecycle management (state rent vs "pay once, store forever")

### Changed

**Design Decisions**
- Expanded comparison table with new rows: scheduled execution, block building, storage model

---

## [2026-01-18] - Document Split and Enhancement

### Added

**Design Decisions (`cowboy-design-decisions.md`)**
- New **Consensus Philosophy** section explaining Simplex BFT choice, mandatory proposer rotation, and MEV resistance strategy
- New **Economic Model** section covering deflationary basefee burning, validator rewards, runner marketplace, and state rent
- New **Entitlements: Least-Privilege by Default** section explaining the permission system philosophy

**Technical Whitepaper (`cowboy-technical-whitepaper.md`)**
- Cross-reference to Design Decisions for application examples

### Changed

**Design Decisions**
- Moved **Applications** section to end of document as a "what you can build" conclusion
- Updated document date to 2026-01-18

**Technical Whitepaper**
- Shortened **Applications** section to avoid duplication (now references Design Decisions)
- Updated document date to 2026-01-18

### Document Structure

The whitepaper is now split into two complementary documents:

| Document | Purpose | Audience |
|----------|---------|----------|
| `cowboy-design-decisions.md` | Architectural rationale, trade-offs, "why" | Developers, investors, general technical |
| `cowboy-technical-whitepaper.md` | Complete specifications, parameters, "how" | Implementers, auditors, protocol developers |

---

## [2025-12-14] - Initial Split

### Added
- Created `cowboy-design-decisions.md` - extracted design rationale from monolithic whitepaper
- Created `cowboy-technical-whitepaper.md` - complete technical specifications

### Removed
- Deleted `cowboy-whitepaper.pdf` (replaced by markdown documents)

### Notes
- Original monolithic whitepaper (`cowboy-whitepaper.mdx`) retained for reference
- New documents include cross-references to each other

---

## Template for Future Entries

```markdown
## [YYYY-MM-DD] - Brief Description

### Added
- New sections or content

### Changed
- Modified existing content

### Removed
- Deleted content

### Fixed
- Corrections to errors

### Notes
- Any additional context
```
