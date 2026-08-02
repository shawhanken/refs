# Situation Report: Inherent Structural Issues in the CIP Framework and Their Impact on Issue Remediation

**2026-08-01**

---

## 1. Overall Status

Remediation is holding a steady pace of roughly **10+ issues per day**, with 100+ remaining and a target of **August 24**. **The large majority of issues complete through the normal flow and pass verification.** However, since last week a small subset of issues, once implemented in depth, have surfaced a class of problem that **does not stem from implementation difficulty but from the specification itself** — a few PRs required seven or eight, even a dozen, rounds before it became clear they could not converge, and **had to be closed without merging (rather than merge-closed after resolution)**. This report focuses on the root of that class of problem: it lives **at the CIP-framework level**, and needs to be addressed at the specification level with all parties.

---

## 2. The Problem: Inherent Structural Issues in the CIP Framework

The root cause in one sentence: **we are currently solving 3 unknowns against 4–5 equations.** From the vantage of the single CIP a given issue references, its fix is a "valid solution"; but the whole project is co-constrained by **dozens of interlocking CIPs** plus the full implementation, and that solution **no longer holds** when substituted into the other CIPs' constraints. This is not a matter of any single fix being done poorly — it is an inherent property the CIP framework has exposed as it has **grown and evolved over a long period**. At its core are **redundant definition of the same responsibility (over-definition)** and **under-specified / undecided semantics (gaps)**. At the issue level it recurs in four forms:

| # | Form | Root cause traced to the CIP framework |
|---|------|----------------------------------------|
| **A** | **Over-constrained / deep conflict**: only at implementation depth does it emerge that no fix can satisfy all CIPs simultaneously — the issue must be abandoned | The constraint count across dozens of CIPs exceeds the design's degrees of freedom; redundant definitions + latent conflicts |
| **B** | **One issue on the surface is actually several** | A single CIP requirement often spans multiple mechanisms/lanes, forcing the work to be split into several independent issues |
| **C** | **~60% of an issue clearly needs doing; whether the other ~40% is needed is unclear** | The CIP does not clearly delineate "must implement vs. optional hardening," so the issue bundles a genuinely-needed fix with uncertain additions |
| **D** | **Issues overlap / conflict with one another** | The CIP surface is broad and interwoven; an issue derived from a local view cannot account for the whole and collides with already-defined / already-implemented functionality |

**Why it is especially hard**: *literal* inconsistencies between specs are relatively easy to find, and we have largely cleared those. The hard class is this one — **each description is more or less correct within its own CIP, and the contradiction surfaces only inside the macro structure where dozens of CIPs co-constrain, and only once the work has gone deep.** This is a new situation that concentrated starting last week and had not been encountered before.

---

## 3. Worked Examples and Root-Cause Analysis (one real case per form)

All cases below are **dormant implementations** — zero impact on the live network on the day they merge; the problem is entirely about "what happens at the moment of future activation."

### A · Over-constrained / deep conflict — COW-1150 (over-definition) and COW-2552 (semantic gap)

**COW-1150**: attempted to add an authorization / anti-abuse gate for "event subscription." On closer work it emerged that the protection it wanted to add **is already provided by CIP-29** (minimum prepaid fee, registration fee, per-topic subscriber cap, emitter-side forced unsubscribe), and the permission it enforces **is not in the normative registry** — activating it would instead **permanently break existing functionality**.
> **Root cause**: a textbook case of "over-definition" — **two places in the spec describe the same thing.** The problem is not the implementation but that the spec gives two definitions for one responsibility. Abandoned (won't-do); the way forward is spec-level consolidation.

**COW-2552**: aimed to defer classification of nodes that "reveal late within the window." Only **after multiple rounds** did it surface that, once activated, the mechanism would **penalize the wrong party** — an honest node foreclosed from revealing by early settlement is indistinguishable from a genuine non-revealer and gets wrongly slashed, while the actual attacker escapes.
> **Root cause**: the CIP **left a gap** on the key semantic question "does early settlement foreclose a reveal, and is such a node slashable?" Once that was clarified and the design reworked, a corrected version was successfully delivered — proving that **spec-first** is the only viable path.

### B · One surface issue, actually several — COW-2891 → COW-2897

COW-2891 called for "excluding slashed dissenting nodes from settlement payout." It looked singular, but implementation revealed **two independent settlement lanes** (cash settlement + CIP-10 container-compute settlement), with different constraints that **cannot be handled together in one place** (merging them would perturb the other lane's immediate-settlement decision). It therefore had to be **split into two issues**: COW-2891 for the cash lane and a new **COW-2897** for the container lane.
> **Root cause**: a single CIP requirement spans multiple mechanism lanes; "one issue" is really "a set of issues." Both were delivered correctly.

### C · ~60% clearly needed, ~40% uncertain — COW-2700

COW-2700 bundled two parts: (a) a **genuine mailbox-message leak fix** (clearly needed), and (b) a **per-sender quota** (necessity unclear). On closer work it was confirmed that the mailbox **drains every block**, so a single sender is already bounded by the existing cap and quota (b) is **redundant**. In the end **(a) was kept and merged, and (b) was fully reverted** — the merged PR title literally reads "quota dropped."
> **Root cause**: the CIP does not delineate "what must vs. need not be done" for this scenario, so the issue bundled a genuinely-needed fix with uncertain hardening. About 60% landed; 40% was cut after review.

### D · Issues overlapping / conflicting — COW-2702

COW-2702 called for implementing two card instructions for BankActor — **TransferOwnership + SetPolicy**. But those two instructions (`BankTransferOwnership`, `BankSetPolicy`) **had already been implemented and merged into devnet by prior BankActor work (COW-1134 et al.)**. COW-2702, at generation time, **did not cross-check the already-completed related issues**, and is therefore a **duplicate / overlapping issue** (recommended to close as Done).
> **Root cause**: the CIP surface is broad and interwoven; an issue derived from a local view collides with functionality already implemented globally — doing it would be wasted rework.

---

## 4. Conclusion and Coordination Needs

1. **This is an inherent property of a large, evolving specification, not a point failure**: dozens of CIPs evolving over time and co-constraining will inevitably produce, in certain regions, **over-definition, semantic gaps, and overlap among derived issues.** This class of problem **cannot be solved by adding implementation effort** — it can only be identified and consolidated at the specification level.
2. **What we are doing**: systematically auditing dozens of CIPs for **redundant definitions and latent conflicts**, locating the "over-constrained" points ahead of time, and separately flagging issues that are **spec problems in nature, not code problems.**
3. **Coordination needed**:
   - For **over-defined** CIPs, **consolidate / de-duplicate** (make clear which single CIP uniquely owns a given responsibility);
   - For CIPs with **semantic gaps**, **fill in the definition or explicitly de-prioritize / defer**;
   - For **overlapping / conflicting** issues, cross-check the whole, de-duplicate and merge, and **re-prioritize** accordingly.

**Bottom line**: the earlier these structural problems are identified and clarified at the spec level, the more we avoid the rework loss of "implementing repeatedly for hours only to find the whole thing cannot proceed" — and this is the most effective way to safeguard the August 24 target.

---

## Appendix: Issues Matching Patterns B / C / D

> Note: this list contains only items **substantiated by recent review and processing records**; it is **not exhaustive.** A full audit of the remaining 100+ issues is precisely the work the "review" requested in Section 4 is meant to complete jointly. It is **restricted to PRs / issues owned by our side (shawhanken / freemanhuke / pavilionledger)** — comparable problems encountered by other development parties are not included. Evidence tiers: **code / PR = first-hand verification**; **internal record = our review / triage judgment.**

### Pattern B — one surface issue, actually several

| Issue | Manifestation | Evidence / Root cause |
|---|---|---|
| **COW-2891 → COW-2897** | "Exclude slashed dissenters from payout" split into two issues — **cash lane + CIP-10 container lane** (different constraints, cannot be handled together) | PR #1207 body explicitly a follow-up to #1203 (first-hand) |
| **COW-2504** | A single "billing → CAE" goal spanning **7+ PRs** (node #1168/#1170/#1175/#1183 + runner #194/#195), of which **#1176 is a fix-forward for #1175** | gh PR list (first-hand) |
| **COW-2699 / COW-2701** (#1194) | One "ToB residuals" cleanup **bundling two tickets in the same PR**, and **deferring COW-2700** separately | #1194 title (first-hand) |
| **COW-2721 → COW-2722** (#1195) | "Shut down node to avoid a p2p zombie" spawned COW-2722 (node-identity robustness) as a sub-item | Internal review record |
| **COW-2894** (#1205) | Review of "minimum governance tier" found a follow-up item — ExecutorRegistryPin/Unpin **need a submit-gate added** | Internal review record |

### Pattern C — ~60% clearly needed, ~40% uncertain

| Issue | Manifestation | Evidence / Root cause |
|---|---|---|
| **COW-2700** (#1196) | Bundled "mailbox leak fix (needed)" + "per-sender quota (necessity unclear)"; on closer work the **quota was judged redundant and fully reverted**, keeping only the leak fix | Merged PR title reads "quota dropped" + author comment "quota fully reverted" (first-hand) |

> This pattern is relatively rare among items **already processed**; COW-2700 is the clearest instance. More cases require delineating "must implement vs. optional hardening" per issue during the joint review.

### Pattern D — issues overlapping / conflicting

| Issue | Manifestation | Evidence / Root cause |
|---|---|---|
| **COW-2702** (pavilion) | The BankActor TransferOwnership / SetPolicy it asks to implement were **already implemented and merged into devnet by prior BankActor work** | Code `BankTransferOwnership`/`BankSetPolicy` already present (first-hand); recommend close as Done |
| **COW-1024** (pavilion) | While implementing CIP-12 governance, its proposal opcodes **103–107 collided with CIP-16**, requiring uniqueness coordination | Our implementation record + the `sys_opcode_uniqueness` invariant |
| **COW-1150** (#1193, see §3-A) | Our PR's subscription authorization **duplicates the existing CIP-29 mechanism** — also a case of "overlap with existing work" | Cross-reference §3-A (first-hand) |

---

*Compiled from the 2026-08-01 internal review and the actual handling records of the issues above; stated faithfully without exaggeration. The appendix list is a substantiated subset, not exhaustive.*
