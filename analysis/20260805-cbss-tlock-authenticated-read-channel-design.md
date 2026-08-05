# CBSS tlock signer trusts an unauthenticated node endpoint — authenticated-read design (COW-2889 residual)

**Status:** verified LIVE residual (2026-08-05). Consensus-adjacent (trust-anchoring the committee-side chain reads) — implement deliberately, crypto/consensus-owner review required. Do **not** drive-by.
**Repo:** cbss (`crates/cbssd/src/main.rs` tlock serve loop; `crates/cbssd/src/chain_watcher.rs`). Authoritative counterpart: node (`execution/src/cbss.rs`, `rpc/src/handlers/proof.rs`).
**Related, already landed:** #78 (COW-2889, defense-in-depth reveal-height gate); the `/logs`-decoupling liveness fix (`fix/cbssd-tlock-gate-liveness-decouple-logs`, this session). Both are necessary but neither closes the residual below.

## 1. Symptom / threat

cbssd's committee-side tlock signer (`serve_due_tlock_requests`, `crates/cbssd/src/main.rs:1253`) produces a BLS partial `σ_i = s_i · I_tlock(tag, target_height)` for each request its node reports as "due". Every input it leans on comes from **one** unauthenticated `cfg.chain.node_endpoint` (`main.rs:312`, the sole arg to `ChainWatcher::new`), over routes that share that origin:

- `GET /cbss/tlock-requests/{proxy_id}` — the due-set: `(scope, tag, target_height, committee_epoch, proxy_index, vss_commitments)` (`chain_watcher.rs::tlock_requests`).
- `GET /height` — the chain head that the #78 reveal-height gate compares against (`chain_watcher.rs::chain_head`).
- `GET /actor/0x…04/logs` — CBSS event heights, also folded into the head.

A party controlling that `node_endpoint` for ≥ `t` proxies (a shared/malicious RPC provider, or a network-position interposer) can therefore forge, consistently across all routes:

1. **Timing (COW-2889 core, live-fire verified).** Advertise a not-yet-due request with a forged high `/height`, harvest ≥ `t` premature partials, Lagrange-combine `σ = MSK · I_tlock`, and **decrypt any tlock / CIP-34 sealed bid before its reveal height** — front-running settlement auctions.
2. **Identity (CIP-24 §3.4.6 clause 2, unimplemented).** Present a due-set entry with an **arbitrary `tag`/`scope`** that the chain never registered. cbssd signs `σ_i = s_i · I_tlock(tag, h)` for an identity outside the on-chain set. The node's own read path refuses this — `tlock_requests_for_proxy` loads the backing record and returns `TlockNotRegistered` for anything unregistered (`node/execution/src/cbss.rs:4175`, gate at `:1611-1613`) — so **cbssd currently signs a strictly larger identity set than the chain accepts**.

## 2. Why the obvious fix (corroborate against the same node) does NOT work

The intuitive clause-2 fix is: before signing, independently read the on-chain `TlockRequest` and check the due-set entry against it. The node stores it at `tlock_req:{id}` on `CBSS_SYSTEM_ACTOR` (0x04), keyed by `id = tlock_id(scope, tag, target_height) = keccak256(canonical(scope) ‖ le(len(tag)) ‖ tag ‖ le(target_height))` (`node/execution/src/cbss.rs:3870,3878`), readable over `GET /state/0x…04/{key}` (`node/rpc/src/handlers/proof.rs:351`).

But that read would go to **the same `node_endpoint`**. Against the threat in §1 it is **circular** — an interposer forges the `/state` response identically to the due-set. Against an honest node it is a **no-op** — the node only surfaces due requests it has already loaded the backing record for, so the due-set is always consistent with `/state`. Either way it adds no security while adding a byte-for-byte replica of the node's `tlock_id`/`canonical(scope)` derivation (consensus-adjacent drift risk requiring a cross-repo KAT). This is the "guard derived from the same untrusted source it guards" anti-pattern; it must be rejected.

**Corollary:** clauses (1) timing and (2) identity are the *same* problem. Both are closed exactly when the committee-side chain reads become **authenticated / independently anchored**, and neither is closed by any same-endpoint check. This document is about that anchor.

## 3. What "authenticated" has to mean here

cbssd must be able to reject a forged read using data an interposer on a single `node_endpoint` cannot fabricate. Three viable anchors, in increasing strength/cost:

### Option A — Multi-endpoint quorum (cheapest; no node/protocol change)
Configure cbssd with `N` independent node endpoints. Read `/height`, the due-set, and (if desired) the `TlockRequest` from all of them; require agreement from a configured quorum `q` (e.g. `q = ⌊N/2⌋+1`) on `(head, {registered requests})` before signing; withhold on disagreement.
- **Closes:** an interposer must now control `q`-of-`N` distinct endpoints, not one. Reduces trust to "≥ `N−q+1` honest endpoints".
- **Cost:** config surface + fan-out reads + a reconciliation/withhold policy. No node change, no byte-canonicality replica (compare decoded values, not keys).
- **Limit:** not cryptographic — collusion of `q` endpoints (or a shared upstream they all proxy) still forges. Good defense-in-depth, weak against a determined interposer who sits above all endpoints.

### Option B — CIP-17 verifiable state read against an independently anchored state root (cryptographic; needs a root anchor)
The node already serves inclusion/exclusion proofs: `GET /state/0x…04/{tlock_req:id}?prove=true` returns a Merkle proof + value + the committed `state_root` (`node/rpc/src/handlers/proof.rs:419-455`). cbssd verifies the proof, so a forged registration is caught **iff cbssd independently knows the correct `state_root`**.
- The proof reduces the problem from "trust the whole response" to "trust one 32-byte root". But the root still arrives from the node — so this Option is only complete when combined with a trustworthy root source (Option C, a checkpoint feed, or the same quorum of Option A applied to the root alone).
- Handles **identity** (registration) cleanly. **Timing** needs the analogous move: bind `target_height`-reached to a proof/anchor of the head, not a bare `/height`.

### Option C — Consensus-signed head / finality certificate (strongest; needs node support)
Have the node expose validator-signed block headers (or reuse an existing finality artifact — cf. the CIP-25 `finalized:` anchor machinery in `node/rpc/src/handlers/anchor.rs`, and the native/eth light-client finality work in node). cbssd verifies the signatures against the known validator/committee set and uses that authenticated head both as the reveal-height source and as the anchor for Option B's state root.
- **Closes both clauses cryptographically**, independent of how many RPC endpoints the interposer controls.
- **Cost:** node must expose signed headers; cbssd must track the validator set and verify BFT signatures. Largest change, but the only one that fully closes the live-fire exploit against a single-channel interposer.

## 4. Recommendation

1. **Ship the two already-scoped pieces** (done / in review): the #78 defense-in-depth height gate and the `/logs`-decoupling liveness fix. They bound blast radius and remove the self-inflicted DoS, but must not be described as closing COW-2889.
2. **Target Option C as the durable fix**, using Option B as its state-read mechanism once an authenticated `state_root`/head exists. This closes timing and identity together and is the only choice robust to a single-endpoint interposer — the actual threat model.
3. **Option A is a reasonable interim** if C is far off: it is pure cbssd config+code, raises the bar from one endpoint to a quorum, and is composable with B/C later. Frame it honestly as defense-in-depth, not a cryptographic close.
4. **Explicitly do not** implement same-endpoint corroboration (§2). It is security theater and adds a consensus-adjacent byte replica.

Scope note for the tracking ticket: reframe the COW-2889 follow-up from "authenticate `/height`" to **"authenticate/independently-anchor the committee-side chain reads (head + registration)"** — both §1 clauses, one anchor.

## 5. Risk / review

- **Owner:** crypto/consensus. Option C touches validator-set tracking + BFT signature verification; Option B touches Merkle-proof verification; both are consensus-adjacent.
- **Liveness coupling:** any anchor that can fail-closed (no quorum, stale root, unverifiable header) must withhold, not sign — and withholding interacts with CIP-34 `AUCTION_GRACE`. Ensure the anchor's availability budget is well inside the grace window, or auctions get cancelled (the same failure mode the `/logs`-decoupling fix just removed).
- **Determinism:** the reveal-height boundary must stay byte-identical to the node's `current_block < target_height` gate (`node/execution/src/cbss.rs`), regardless of anchor.

## 6. Test approach

- Negative (identity): a due-set entry with a `tag` absent from the anchored state → withheld; positive: a registered `(scope,tag,target)` → signed.
- Negative (timing): an anchored head below `target_height` → withheld even when a rogue `/height` reports it reached.
- Interposer model: a mock that forges one endpoint's `/height`+due-set while the anchor (quorum peers / signed header / verified root) disagrees → no partial emitted. This is the test the same-endpoint corroboration provably cannot pass, and the reason for the anchor.
