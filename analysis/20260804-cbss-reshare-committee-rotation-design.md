# CBSS reshare cannot rotate committee membership — verification + fix design

**Status:** verified LIVE + spec-supported (2026-08-04). Fix scoped below; protocol-adjacent (threshold-crypto ceremony) — implement deliberately.
**Repo:** cbss (`crates/cbssd/src/orchestrator.rs`, `reshare_driver.rs`). Reachability driver: node (`execution/src/cbss.rs`).

## 1. Symptom

A CIP-24 reshare whose **new committee does not fully contain the old signers** stalls: the ceremony never qualifies dealers, so `RotateCommittee` is never submitted. Only same-committee (or high-overlap) refresh works.

## 2. Why it is LIVE (not latent)

- **Node emits disjoint-capable reshares.** `handle_cbss_request_reshare` computes the reshare dealers as `old_signer_proxies = active_old_signer_proxies(store, &material.old_committee, threshold)` (`node/execution/src/cbss.rs:5097-5098`) — the first `threshold` non-suspended proxies of the **old** committee, in order, with **no filter to the new committee**. `new_committee` is an independent, caller-supplied set (`cbss.rs:5017`), validated only for size/sigs/MPK; there is **no old∩new overlap requirement** anywhere in `RequestReshare`.
- So a `RequestReshare` from `{1,2,3}` to `{4,5,6}` emits `old_signer_proxies = {1,2}` (⊆ old), disjoint from new `{4,5,6}`.

## 3. Why full rotation is INTENDED (spec)

- CIP-24 §3.6.2: `committee: Vec<ProxyId> // current committee … **mutable on reshare**`; `committee_epoch increments on each successful reshare`.
- CIP-24 §5 impl note: *"Proactive secret sharing (committee resharing) … CBSS implements a thin wrapper following **drand's published resharing protocol**"* — in which the **old** group re-deals the secret to a **new** group; `MSK` (=`MPK`) is preserved across the change. Full membership rotation is the designed capability.

So the dealers of a reshare are, correctly, the **old** signers (they hold the shares and re-deal them). The new committee are the **recipients**.

## 4. Root cause (cbssd — systemic in the reshare ceremony state)

The orchestrator's per-ceremony `CeremonyState` stores the **new** committee in `self.committee` and the old in `self.prior_committee` (`orchestrator.rs:99,110`, populated for reshare at `:466`/`:708`). But every DEALER-side check defaults to `self.committee` (new), which is correct for DKG (dealers = new members dealing to themselves) and **wrong for reshare** (dealers = old signers):

- **`qualify_dealers`** (`orchestrator.rs:180-192`): `validate_proxy_subset(&self.committee, self.threshold, &qualified_dealers)` — validates the reshare dealers against the **new** committee. `qualify_reshare_dealers` (`:1061`) → 6-arg `qualify_dealers` (`:1565`) → `state.qualify_dealers` (`:180`), so the reshare path routes straight into this new-committee check. Old signers ∉ new committee → rejected. **This is the primary stall.**
- **`active_dealers`** (`:176-178`): `self.qualified_dealers.as_deref().unwrap_or(&self.committee)` — before qualify, the dealer set defaults to the **new** committee.
- **`ensure_active_dealer`** (`:168`) / **`ensure_proxy`** (`:160`): membership checks against `active_dealers()` / `self.committee`. If the reshare Round2 dealer ingest (`ingest_reshare` Round2 → `state.ingest`, `orchestrator.rs:1030`) validates the sender against these, an old dealer ∉ new committee is rejected before its dealt shares are recorded — a second manifestation.

Net: for a reshare, the DEALER pool must be `prior_committee`, not `committee`; the current code conflates the two.

## 5. Fix approach

Introduce a ceremony-kind-aware **dealer pool** and route all dealer-side checks through it:

```
fn dealer_pool(&self) -> &[ProxyId] {
    match self.kind {
        CeremonyKind::Reshare => &self.prior_committee,   // old signers re-deal
        _ /* Dkg */           => &self.committee,          // members deal to themselves
    }
}
```

Then:
- `qualify_dealers` (`:192`): `validate_proxy_subset(self.dealer_pool(), self.threshold, &qualified_dealers)`.
- `active_dealers` (`:177`): `self.qualified_dealers.as_deref().unwrap_or(self.dealer_pool())`.
- The Round1/Round2/Commit ingest sender checks: a reshare **dealer** message (Round2/Commit) must be validated against `dealer_pool()` (old), while a reshare **recipient/Round1** announcement (`start_encrypted_reshare_shared`, `reshare_driver.rs:95`) stays against `committee` (new). Audit each `self.committee.contains` / `ensure_proxy` / `ensure_active_dealer` call on the reshare code path and split recipient-vs-dealer intent.
- `finalize_reshare_output` (`:1593`) already iterates `active_dealers()` for `round2` — it becomes correct once `active_dealers()` returns the old pool.

**Do NOT** "fix" this on the node side by constraining `old_signer_proxies ⊆ new_committee` — that would silently forbid the rotation the spec grants and defeat proactive resharing.

## 6. Risk / review

This is threshold-crypto ceremony orchestration. Getting the dealer/recipient split wrong risks either (a) a **liveness** regression (rejecting valid dealers — the current bug) or (b) a **security** regression (accepting shares from the wrong set, or letting a non-old proxy inject a dealer message). Every touched membership check must be classified recipient-vs-dealer with care, and the change wants crypto-owner eyes (the resharing wrapper is already flagged for external review, CIP-24 §5). The `finalize`/VSS-consistency checks (`reshare.rs:330-359`, MPK-preservation `reshare.rs:293`) are the backstop that a mis-set dealer pool would trip — useful as a test oracle.

## 7. Test approach

Current reshare driver tests use `old == new` (`reshare_driver.rs:504`). Add an end-to-end reshare with a **disjoint (or partially-overlapping) new committee**:
- `{1,2,3}` (threshold 2) → `{4,5,6}`; drive Round1 (new announce) + Round2 (old signers `{1,2}` deal) + Commit + qualify, and assert the ceremony reaches `Committed` and produces a `RotateCommittee` whose `new_mpk == old_mpk` (MSK preserved) and whose share validly partial-signs an identity wrapped under the preserved MPK.
- A negative: a Round2 from a proxy **not** in the old committee is rejected.

## 8. Recommendation

The bug is confirmed live and spec-supported, and the fix is now well-scoped (§5). Because it is a multi-point change in a threshold-crypto ceremony, land it as a focused PR **with the disjoint-committee e2e test as the gating oracle** and crypto-owner review — not as a drive-by. (Node side needs no change; it already emits the correct disjoint reshare.)
