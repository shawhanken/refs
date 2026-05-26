# Whitepaper Changelog

All notable changes to the Cowboy whitepaper documents are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
  - 17.6 Off-chain blob storage via CIP-7
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
