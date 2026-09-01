# Decision proposal — CIP-30 O(1) fork vs CIP-27 sealed-storage exclusion

**Issue:** cowboyinc/cowboy#236 (audit HIGH H-8) · **Status:** open, needs owner decision · **Class:** cross-CIP design (governance) — *this doc recommends, it does not decide.*

## The conflict

Two normative MUSTs cannot both hold as written:

- **CIP-30 §3.4** requires `fork()` to set `child.storage_root = parent.storage_root` **unconditionally** ("the child's storage IS the parent's, as of the moment of fork") — an **O(1)** root-hash copy that inherits the *entire* parent trie.
- **CIP-27 §3.3** requires that **CIP-24 sealed-secret-bearing storage entries** (those "declared by the parent's manifest as CIP-24-sealed") **MUST be excluded** from the storage copy; the child rebuilds them in `on_fork` if needed.

A root-hash copy inherits every key, sealed entries included. Excluding them means building a *different* trie than the parent's, which is not an O(1) root copy. CIP-30 never mentions CIP-24 sealed storage.

## Key technical facts (grounded)

1. **The sealed set is known, not discovered.** CIP-27 §3.3 says the excluded entries are the ones "declared by the parent's manifest as CIP-24-sealed" — i.e. an *eligibility list* available from the manifest, not something requiring a full-trie scan. So a filter set of exactly which keys to drop is cheaply available at fork time.
2. **Inherited sealed ciphertext is useless to the child.** CIP-27 §3.3: the wrapped DEKs are "bound to the parent's identity-derived key"; the child "cannot re-key parent-sealed material in-band." So even if the child inherited the sealed ciphertext, it **cannot decrypt it**. The exclusion is therefore a **correctness/hygiene** requirement (don't carry undecryptable parent ciphertext into the child's committed state), **not** a confidentiality gate — confidentiality already holds cryptographically.
3. CIP-24 uses two-layer access control (manifest ∩ ACL, §10.5), but that governs *release*, not the trie-copy semantics at issue here.

## Options

### (a) Filtered fork trie
Build the child's storage as a new trie = parent trie **minus** the manifest-declared sealed keys.
- ✅ Cleanest semantics: the child's committed state never contains parent-sealed ciphertext.
- ❌ **Loses O(1)** whenever the actor has *any* sealed storage — cost is O(total keys) or at least O(sealed keys) with structural sharing. Defeats CIP-30's headline property for exactly the security-sensitive actors.

### (b) O(1) root-copy + runtime deletion of the sealed set  — **recommended**
`fork()` keeps the unconditional O(1) `child.storage_root = parent.storage_root`; **immediately afterward, the runtime deletes the manifest-declared CIP-24-sealed keys from the child trie** (before the fork transaction commits).
- ✅ **Common case stays O(1)** — actors with no sealed storage pay nothing extra.
- ✅ Actors *with* sealed storage pay only **O(sealed-key-count)** deletions, bounded by the manifest declaration (not the full trie).
- ✅ Honors CIP-27's exclusion MUST: the child's *committed* state contains no parent-sealed entries.
- ✅ The transient presence (between root-copy and deletion) is **within the same atomic fork transaction**, never externally observable, and harmless anyway because the ciphertext is undecryptable by the child (fact 2).
- ⚠️ The deletion MUST be a **runtime step**, not delegated to the actor's `on_fork` Python callback (an actor could omit it, silently violating the MUST). `on_fork` may still *rebuild* sealed state it wants; it must not be trusted to *remove* it.

### (c) Drop the CIP-27 exclusion; document inheritance as harmless
Amend CIP-27 to allow the O(1) copy to carry parent-sealed ciphertext into the child, documenting that it is inert (undecryptable, crypto-bound to the parent).
- ✅ Simplest; pure O(1) always.
- ❌ The child's committed state permanently carries the parent's sealed ciphertext → state bloat proportional to parent secrets, a surprising invariant ("your fork contains my sealed blobs"), and a latent footgun if the identity-derivation scheme ever changes or a future feature lets a child assume the parent's identity. Trades a clean security boundary for a small constant of O(1) purity.

## Recommendation

**Option (b).** It preserves CIP-30's O(1) property for the overwhelming common case (no sealed storage), pays a bounded O(sealed) cost only for the actors that actually hold sealed material, and satisfies CIP-27's exclusion MUST in *committed* state. The safety of the transient in-trie presence is underwritten by the cryptographic parent-identity binding, so there is no confidentiality regression.

**Required normative edits (both CIPs, to be kept in lockstep):**
- **CIP-30 §3.4:** add: after the O(1) root-copy, the runtime MUST delete every key the parent manifest declares CIP-24-sealed from the child trie before commit; note O(1) holds except O(sealed-key-count) for sealed-bearing actors; cross-reference CIP-27 §3.3.
- **CIP-27 §3.3:** state that exclusion is realized by post-copy runtime deletion (not by the actor's `on_fork`), and that inherited-then-deleted material would be undecryptable regardless.

## Decision owners
CIP-27 + CIP-30 owners (jointly). Economics not involved. No consensus-value change to a running chain beyond the fork semantics themselves; treat any implementation as flag-day (changes state-root derivation for forks with sealed storage).

---
*Generated as an audit follow-up recommendation (2026-07-12). Advisory only — the CIP owners decide.*
