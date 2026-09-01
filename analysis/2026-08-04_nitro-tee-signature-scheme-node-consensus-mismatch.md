# Nitro TEE signature scheme — do NOT drive-by "fix"; it is unbuilt CIP-23 P3

**Status:** verified (2026-08-04). The on-chain `SubmitTeeAttestation` / `verify_tee_quote_signature` path is a **stub** pending the CIP-23 P3 CAE/SNARK pipeline. The "Nitro should be ES384" framing (and the earlier "runner 96→64") are BOTH wrong. No self-contained code fix exists; this is a P3 design decision for the TEE owner.

**Repos:** node (`execution/src/cbss.rs`), runner (`crates/runner-tee`, `crates/chain-client`). Evidence only — **no change recommended in either without a TEE-owner design decision.**

## 0. TL;DR — three readings, each refuted by deeper evidence

1. *"Runner requires 96 for Nitro, node wants 64 → change runner to 64."* **Wrong:** a real Nitro enclave emits a 96-byte ES384 COSE_Sign1 sig (`runner-tee/src/nitro_collector.rs:20` — "ES384, the only scheme Nitro emits"); it cannot produce a 64-byte Ed25519 sig.
2. *"Node verifies Nitro as Ed25519 → the node has the algorithm wrong; fix = P384/ES384 like SEV-SNP."* **Wrong:** (a) the node's Nitro=Ed25519 is deliberate and spec-cited — `normalize_tee_public_key` comment "Nitro uses the v3 Ed25519 **service** key (§3.5.1)"; (b) a bare `P384VerifyingKey::verify(signing_bytes, sig)` cannot validate a COSE_Sign1 anyway — the ES384 sig is over the COSE `Sig_structure`, not the node's `signing_bytes`.
3. *"Then the node correctly verifies the CIP-23 service_sig (Ed25519) → the runner should submit the service_sig."* **Also not quite:** the node does **not** verify the CIP-23 service_sig either. `tee_attestation_signing_bytes` (`cbss.rs`) is a **node-invented** preimage `TEE_ATTESTATION_SIG_DOMAIN ‖ job_id ‖ runner ‖ len(tee_type)‖tee_type ‖ measurement_hash ‖ expires_at_block ‖ attestation_data` — it is neither the COSE `Sig_structure` nor the CIP-23 §3.5.1 `service_sig` preimage `scope_id ‖ req_hash ‖ result_hash ‖ attest_digest`.

So the current path matches **no** normative CIP-23 signature. It is a placeholder.

## 1. What the current on-chain path actually is (stub)

`handle_submit_tee_attestation` (`cbss.rs`): looks up pre-registered `TeeTrustedKeyIndex.public_keys` by `(tee_type, measurement_hash)`, then accepts if **any** trusted key verifies `quote_signature` over `tee_attestation_signing_bytes` using the per-tee_type algorithm in `verify_tee_quote_signature`: P256 (SGX/TDX), P384 (SEV-SNP), **Ed25519 (Nitro)**. `normalize_tee_public_key` enforces the matching key format per type (64/65-B SEC1 P256; 96/97-B SEC1 P384; 32-B Ed25519).

This is a self-consistent toy: whoever holds the registered trusted key signs a node-defined blob. It is **not** CPU-quote verification (the real CPU quote `CpuAttestation.quote` is "verified inside the SNARK, §3.8", CIP-23 line 125) and **not** the CAE service_sig (§3.5.1).

## 2. What CIP-23 actually specifies (for when P3 is built)

- **CPU quote** (Nitro): raw `COSE_Sign1`, `protected = {1:-35}` (ES384), `signature` = 96-byte `r‖s`; `payload` carries `pcrs`, `certificate` (leaf DER), `cabundle` (chain, root-first), `user_data = REPORTDATA` (CIP-23 §… doc-shape, line 400). Verified in-SNARK at registration; per-call "light path" checks it against the binding's `bound_quote_key` (§3.11.5, line 384).
- **Service signature**: `ServiceSignature { scheme: Ed25519 (v3-only), service_pubkey:[u8;32], sig = Sign(sk, scope_id ‖ req_hash ‖ result_hash ‖ attest_digest) }` (§3.5 struct + §3.5.1 line 183). Ed25519 is **mandatory** in v3 (line 179), EcdsaP256 reserved.

So in the real design a Nitro attestation carries **both** an ES384 CPU-quote sig **and** an Ed25519 service sig — two different signatures over two different preimages, verified by two different mechanisms (SNARK/light-path vs direct). The current single-`quote_signature` stub collapses this and invents its own preimage.

## 3. Why there is no correct drive-by fix

Any change to `verify_tee_quote_signature`'s Nitro arm is a **consensus change** whose "correct" target is undefined until P3 decides which real signature the on-chain path verifies:

- If it should verify the **CPU quote**: needs COSE_Sign1 parsing + ES384 over the COSE `Sig_structure` + cabundle cert-chain to the pinned AWS Nitro root + REPORTDATA binding — not a one-line algorithm swap, and it changes what the runner must submit (the COSE doc, not a blob-sig).
- If it should verify the **service_sig**: needs the preimage changed to `scope_id ‖ req_hash ‖ result_hash ‖ attest_digest` and the runner to sign with the Ed25519 service key — and then it is the same for **all** tee_types (service_sig is type-independent), which contradicts the current per-type P256/P384/Ed25519 split.

Either way the runner side (`runner-tee` quote collection + `chain-client` `quote_signature` construction — itself stub-level, currently shipping the raw COSE bytes, not a signature over the node preimage) must change in lockstep. This is exactly the CIP-23 P3 "upgrade `0x05` from stub into a real attestation pipeline" work.

## 4. Reachability / severity

Liveness, **not** security (the blind-sign class is closed by runner #200/#201/#202). `runner-tee` is placeholder-stage; default generator uses SEV-SNP; Nitro requires an explicit `COWBOY_NITRO_COSE_ATTESTATION_COMMAND`. No fund-drain, no consensus split today (the stub is internally consistent — a Nitro attestation simply never verifies end-to-end). It is a latent gap to close **as part of P3**, before Nitro is advertised as a live backend.

## 5. Recommendation

**Do not** change `verify_tee_quote_signature` (or the runner) as a drive-by — every candidate one-liner is refuted above, and it is a consensus-surface change with an undefined target. File it as a **CIP-23 P3 design item** for the TEE owner: "define the on-chain Nitro attestation verification (CPU-quote COSE/ES384+cert-chain vs CAE service_sig/Ed25519) and align `runner-tee` + `chain-client` + `handle_submit_tee_attestation` in one coherent change." The blind-sign security fixes (#200/#201/#202) are complete and independent of this.
