# CIP-24 amendment draft — Operator-principal release class (account-authorized standing release)

**Status:** DRAFT (refs). Not yet a canonical CIP-24 amendment. This document proposes a v1 amendment; if accepted it is lifted into `cowboy/docs/cips/cip-24-secrets-manager.md` under the governance/spec-review flow.

**Date:** 2026-07-06
**Author scope:** CIP-24 (Cowboy Secret Service). Authorization layer only — no cryptographic change.
**Companion:** `refs/analysis/2026-07-06-cbss-operator-signing-evaluation.md` (this amendment is the concretization of that document's **Model A**).
**References the CURRENT CIP-24** at `cowboy/docs/cips/cip-24-secrets-manager.md` (1671 lines, last amended 2026-07-03 `GovRequestSystemDkg` / opcode 158). Exact section/line anchors below are against that revision.

---

## 0. Summary

CIP-24 today has **two release modes** on the same staked committee:

| Mode | §  | Identity domain | Release trigger | Who may obtain σ |
|---|---|---|---|---|
| Secret release (confidential) | §3.4.3 | `cbss/ibe/v1` | signed `ReleaseRequest`, **ACL-gated** (§3.7) | the authorized **runner** only |
| Time-lock release (public) | §3.4.6 | `cbss/tlock/v1` | chain height ≥ `target_height`, **permissionless** | anyone |

Both authorization paths assume the requester is either **(a)** a **dispatcher-assigned runner** acting for a **deployed actor** with a CIP-6 manifest entitlement (§3.7, §3.8), or **(b)** nobody (public tlock). Neither serves the **operator-signing** use case: an account operator running a **standing off-chain service** (e.g. the CIP-34 chat demo's `server.js`, which signs Cowboy transactions with a secp256k1 key) that needs to reconstruct **its own** secret **on its own cadence**, with **no on-chain job, no dispatcher assignment, and no deployed actor**.

This amendment adds a **third release mode** — the **operator-principal release class** — a **confidential** (not public), **account-authorized**, **standing** release path:

| Mode | Identity domain | Release trigger | Who may obtain σ | Authorization root |
|---|---|---|---|---|
| **Operator-principal release (this amendment)** | `cbss/ibe/v1` (**same** as §3.4.3 — confidential) | signed `OperatorReleaseRequest`, **grant-gated** (§3.7) | the operator's registered **standing service** (holder of `K_auth`) | on-chain `OperatorReleaseGrant`, issued by the secret owner's **account root key** |

**Design invariant (load-bearing):** because the operator secret is **confidential**, the operator class stays in the **same** IBE identity space as §3.4.3 (`cbss/ibe/v1`, per-version identity `I = hash_to_G1(base_aad, "cbss/ibe/v1")`). It releases an **ordinary `SecretVersion`**. It introduces **no new key material, no new DKG, no new domain, no new trust assumption** — it reuses the account's existing committee / `MPK` / shares / PSS exactly as §3.4.3 does. The **only** change is *who may request a release and how they authenticate*. This is the mirror of §3.4.6's "no new key or trust" property, but — unlike tlock — it does **not** change the identity domain, precisely because the released key must stay secret.

---

## 1. Motivation (proposed new §2.4)

> **§2.4 The standing-operator gap.** §3.7/§3.8 bind every confidential release to a *live dispatcher assignment* (`0x02`) for a *deployed actor's manifest entitlement* (§3.1, §5.1). This is correct for CIP-2 off-chain compute — a runner is in the trust path for the duration of a job. But a growing class of Cowboy operators run a **standing off-chain service** that holds a **long-lived signing key** (a Cowboy account secp256k1 key, an EVM bridge key, an LLM-provider key) and uses it continuously, outside any job dispatch. The canonical instance is the CIP-34 demo operator/deployer: `server.js` custodies `.cowboy/key` in plaintext at rest and signs every user-triggered transaction with it. There is no job, no dispatcher assignment, and no deployed actor — so the §3.7 checklist cannot authorize the release, and the key sits in plaintext on a single box.
>
> The operator-principal release class lets such an operator custody that key as an ordinary CBSS `SecretVersion` and reconstruct it **on demand, threshold-gated, revocably, and auditably**, authorized by a **dedicated on-chain grant** rather than a manifest+dispatcher pair.

### 1.1 What it fixes vs. the status quo (plaintext-at-rest)

| Property | `.cowboy/key` plaintext at rest (status quo) | Operator-principal CBSS custody (this amendment) |
|---|---|---|
| Key at rest | plaintext on one box; disk/backup/snapshot theft = permanent key loss | never at rest in plaintext; only an IBE-wrapped `wrapped_dek` on chain + CBFS ciphertext |
| Compromise of the box | **permanent** theft of the raw key | **transient** access to a reconstructed key, only during a live signing window (see §8.9) |
| Revocation | none (key is copyable) | `RevokeOperatorReleaseGrant` stops **future** releases (effective at finality + max proxy cache TTL); a key **already released** inside that window is not un-compromised — rotate `K_sign` (§8.9, F5) |
| Threshold gate | none | t-of-n committee must serve partials |
| Audit trail | none | per-proxy `release_receipt` on chain (§3.5 `SubmitReleaseReceipt`) |
| Auth-key ≠ signing-key | n/a | `K_auth` (release authorization) is separate from `K_sign` (the custodied secret) and from the account root key |

### 1.2 What it does NOT fix — honest limitation (transient reconstruction is inherent)

**Custody does not remove transient in-use reconstruction.** At the instant the standing service signs, `K_sign` (or the LLM/EVM key) is reconstructed **in the service's own memory** — a t-of-n release delivers plaintext to the requester by construction. A single-box compromise *at signing time* still observes it. Only a **TEE-gated** operator service (`grant.tee_required`) moves the reconstruction inside an enclave and removes the plaintext-in-host-memory exposure. **This path is not a free reuse of the runner TEE flow** — it requires the grant-scoped attestation companion specified in **§6a** (a new `0x05` record type; the current `tee_att:{job_id}:{runner}` schema binds to a registered runner the operator service is not). Until §6a ships, a `tee_required` grant is **non-serviceable** (fail-closed) and the transient-reconstruction-elimination claim is **deferred**. Accordingly this amendment firmly claims, on the default path, **plaintext-at-rest elimination + revocability + threshold-gating + audit**; and, **conditional on §6a**, **transient-reconstruction elimination**. It does **not** claim transient-reconstruction elimination on the default (non-TEE) path. (This is the explicit answer to "does custodying the key remove the transient-reconstruction problem?" — no, not by itself, and the TEE path that would is a dependent cross-repo change, not shipped here.)

---

## 2. Three-key separation (proposed new §10.9 rationale)

The operator class deliberately splits three roles that the plaintext-at-rest model conflates into one file:

| Key | Curve | Role | Trust temperature | On chain |
|---|---|---|---|---|
| `K_root` (account root key) | secp256k1 | issues/revokes the grant (`RegisterOperatorReleaseGrant` / `RevokeOperatorReleaseGrant`); can also do `UpdateSecretPolicy` per §8.2 | **cold** (offline; operator custody) | the account address |
| `K_auth` (operator-principal auth key) | secp256k1 | signs each `OperatorReleaseRequest`; day-to-day release authorization | **warm** (on the standing service) | `OperatorReleaseGrant.auth_pubkey` |
| `K_sign` (the custodied secret) | any (secp256k1 Cowboy key, EVM key, API token, …) | the actual secret the service uses (e.g. to sign a Cowboy tx) | reconstructed **transiently** at use | wrapped as an ordinary `SecretVersion` (`wrapped_dek`) |

`K_auth ≠ K_sign` is the core structural improvement: the warm, network-exposed service holds only a **release-authorization** key, never the account root key and never (at rest) the signing key. Compromise of `K_auth` yields **release capability** bounded by the grant's rate limit and revocable via `K_root` — not the signing key itself and not account control. See §8.9.

---

## 3. Specification inserts

### 3.1 New data structure — `OperatorReleaseGrant` (insert in §3.1, after `SecretReleaseKey`)

The on-chain record that authorizes a standing operator service to release a specific secret. Stored at `0x04` keyed by `GrantId`. It is the **account-scoped analog** of the actor path's (CIP-6 manifest entitlement **+** `SecretPolicy.actors` **+** dispatcher assignment) triple — collapsed into one owner-issued record, because the principal is an **account's standing service**, not a deployed actor in a dispatched job.

```
OperatorReleaseGrant {
    grant_id:        GrantId          // == keccak256(canonical(secret_id) || auth_pubkey || u64_le(nonce)); stable grant identity
    secret_id:       SecretId         // { account = owner, key_hash }; the owner's own secret
    version_pin:     Option<u64>      // Some => only this version releasable. None => latest non-pending, AND the grant auto-follows every future non-pending version (adding a new version auto-exposes it to the standing service) — so rotating the secret ALONE does NOT cut off a compromised K_auth; only Revoke does (§8.9, F4). Pin to freeze.
    auth_pubkey:     PublicKey        // K_auth; secp256k1; authenticates each OperatorReleaseRequest
    tee_required:    bool             // if true, the standing service MUST present a live grant-scoped CIP-23 attestation via the §6a 0x05 companion (record keyed by grant_id, NOT the runner-scoped tee_att:{job_id}:{runner}); reconstruction happens in-enclave (removes transient host-memory exposure — §1.2, §8.9). A tee_required grant is non-serviceable until §6a ships.
    max_releases_per_hour: u32        // per-grant rate limit (proxy-enforced; §3.7). ≤ MAX_OPERATOR_RELEASES_PER_GRANT_PER_HOUR (§4)
    expiry:          Option<BlockHeight>  // Some => grant auto-expires; None => until revoked
    service_label:   Bytes            // opaque operator-chosen label for audit/UX (bounded length); never in identity/AAD
    created_at:      BlockHeight
}
```

**Relationship to `SecretPolicy`.** The operator grant is an **independent** authorization path onto the same `SecretVersion`; it does **not** consult `SecretPolicy.actors` (which gates the *actor* path). A secret used **only** by a standing operator service is typically stored with `SecretPolicy.actors = Some([])` (no actor may read it) plus one `OperatorReleaseGrant` — so the *only* way to release it is the operator path. A secret MAY carry both an actor ACL and operator grants simultaneously (dual-use). The `tee_required` flags on the two paths are independent.

**Cross-account.** Unlike `SecretPolicy.actors`, an `OperatorReleaseGrant` is **same-account only**: `secret_id.account` MUST equal the grant's issuing sender. An operator grants a standing service access to **its own** secret; it cannot grant a standing service access to another account's secret (that is the actor-path's cross-account grant surface, §3.1 `SecretPolicy`). This keeps the operator class from becoming a second, weaker cross-account channel.

### 3.2 New instructions (insert in §3.5)

Opcodes are **provisional placeholders** allocated next-free against the `SystemInstruction` enum and the opcode-uniqueness test at impl time, per the §3.3 convention (there is no central normative opcode table). Shown as **154/155** to keep clear of the documented 68–84 range, the tlock 152/153, and gov 158. Add these rows to the §3.3 master allocation table.

#### RegisterOperatorReleaseGrant (opcode 154, provisional)

```
RegisterOperatorReleaseGrant {
    secret_id:       SecretId
    version_pin:     Option<u64>
    auth_pubkey:     PublicKey        // K_auth
    tee_required:    bool
    max_releases_per_hour: u32
    expiry:          Option<BlockHeight>
    service_label:   Bytes
    grant_nonce:     u64              // owner-chosen; disambiguates multiple grants for the same (secret, auth key)
}
```

**Sender:** owner of the account (`K_root`). MUST equal `secret_id.account` (same-account rule, §3.1).

**Validation (chain-enforced):**
- `secret_id.account == sender` (reject `OperatorGrantCrossAccount` otherwise).
- A `SecretVersion` under `secret_id` exists (latest, or `version_pin` if `Some`), and if `version_pin = Some(v)` then that version exists and `pending == false` (reject `SecretPending` / `SecretVersionDeleted`).
- `max_releases_per_hour ≤ MAX_OPERATOR_RELEASES_PER_GRANT_PER_HOUR` (§4).
- `auth_pubkey` is a well-formed secp256k1 public key.
- `len(service_label) ≤ MAX_SERVICE_LABEL_BYTES` (§4); grant quota per account not exceeded (`MAX_OPERATOR_GRANTS_PER_ACCOUNT`).

**Effects:** writes `OperatorReleaseGrant` at `0x04` keyed by `grant_id = keccak256(canonical(secret_id) || auth_pubkey || u64_le(grant_nonce))`. Emits `OperatorGrantRegistered { grant_id, secret_id, version_pin, tee_required }`. Does **not** touch the DEK wrap or the release key — the secret was already stored by an ordinary `SetSecret`.

#### RevokeOperatorReleaseGrant (opcode 155, provisional)

```
RevokeOperatorReleaseGrant { grant_id: GrantId }
```

**Sender:** owner of the account (`K_root`); MUST equal `grant.secret_id.account`.

**Effects:** deletes the `OperatorReleaseGrant`. Emits `OperatorGrantRevoked { grant_id }`. Revocation propagation follows §3.7 (effective at chain finality; a proxy MAY serve against a stale cached grant within `PROXY_CACHE_TTL_BLOCKS`).

**Revocation is a future-release cut-off, not an atomic seal — read this precisely (F5):**

- The stale-cache window is **not** a harmless single straggler. A release needs only `t` partials, assembled **off-chain** in the requester's memory (§3.8.1). If all `t` committee proxies still hold the grant in cache within their TTL — the common case immediately after a `Revoke` lands — a compromised `K_auth` obtains a **full `σ = MSK · I` and decrypts `K_sign`**. The window can yield a **complete release**, not one partial.
- The chain-side revocation check at `SubmitReleaseReceipt` (§3.6) gates **payment/audit only**. Receipts are submitted *after* the requester already reconstructed; rejecting all `t` receipts costs the proxies their fee but does **not** un-leak the key.
- Effective revocation latency is therefore `finality + max(participating proxies' cache TTL) × block_time` — documented and bounded, but the chain cannot close it. This is the operator class's kill-switch; it is a real kill-switch **for future releases** (§8.9 relies on it as such), not a retroactive seal.
- **A key released even once is compromised permanently.** Revocation stops the *next* release; it cannot un-compromise a `K_sign` already handed out in the window. After suspected `K_auth` compromise the correct remedy is to **rotate `K_sign`** (deploy a new `SetSecret` version and re-issue the grant on the new key), not merely `Revoke`. Because `version_pin = None` auto-follows versions (§3.1), rotation-without-revocation is a no-op against a live compromised grant — do **both**.

### 3.3 Release-request shape — `OperatorReleaseRequestBody` (insert in §3.5 near `ReleaseRequestBody`)

The operator variant of the release request. This is a second arm of a `ReleaseRequestBody` principal enum — `Principal::Runner { actor, runner_id, job_id }` (the existing §3.5 body) vs `Principal::Operator { grant_id }` — shown here separately for clarity.

**Normative discriminant (M1 — do NOT defer to impl choice).** The `Principal` enum MUST carry a **leading, authenticated 1-byte discriminant** (`0x00` Runner, `0x01` Operator) as the first byte of the serialization that feeds `request_hash = keccak256(serialize(body))`. Both the **signature-domain string** (`cbss/release-request/v1` vs `cbss/operator-release-request/v1`) and the **verification key source** (runner registry vs `grant.auth_pubkey`) MUST be selected **from that authenticated discriminant inside the signed body**, never from an untrusted outer codec framing tag. This is what makes the two arms unambiguous at the consensus-critical `SubmitReleaseReceipt` dispatch (§3.6): the domain prefix alone stops signature *replay* across arms, but only the in-body authenticated discriminant stops arm *confusion* at on-chain parse/lookup time. An implementation that serializes `OperatorReleaseRequestBody` as a bare struct without this discriminant is non-conforming.

```
struct OperatorReleaseRequestBody {           // unsigned; the message K_auth signs
    secret_id:       SecretId                 // owner's own secret
    version:         u64                       // concrete version (latest resolved, or grant.version_pin)
    grant_id:        GrantId                   // the authorizing grant
    recipient:       ReleaseKeyRef             // Account(owner) default, or SecretSpecific(...) on override
    release_nonce:   Bytes32                   // fresh CSPRNG per pull
    request_block:   BlockHeight               // freshness-checked at submission
    serve_epoch:     u64                       // committee_epoch the service intends partials from; pins quorum_epoch
}

struct SignedOperatorReleaseRequest {
    body:      OperatorReleaseRequestBody
    auth_sig:  Signature                       // sign(K_auth, keccak256("cbss/operator-release-request/v1" || request_hash))
}

request_hash := keccak256(serialize(OperatorReleaseRequestBody))

release_id   := keccak256(u8(0x01) || canonical(body.secret_id) || u64_le(body.version) || body.grant_id || body.release_nonce)
              // Operator-variant release_id: grant_id replaces (actor || runner_id || job_id).
              // L1: leading u8 principal-domain byte (0x01 Operator; runner path takes 0x00 — see §8).
              // keccak256 collision-resistance already makes cross-arm collision infeasible (preimages differ:
              // runner 1+164, operator 1+124 bytes); the leading byte is defense-in-depth against any future
              // field-width change (e.g. a variable-length job_id) reopening structural preimage confusion.
              // Same properties: stable per pull, excludes request_block, drives proxy bloom + chain dedup + quorum cap.
```

New domain-separated signature payload (add to §3.5 "Canonical domain-separated signature payloads"):

```
auth_sig (in SignedOperatorReleaseRequest):
    sign(K_auth_priv,
         keccak256("cbss/operator-release-request/v1" || request_hash))
```

The **identity binding is unchanged** from §3.4.3: `base_aad = canonical(SecretId) || u64_le(version) || u64_le(wrap_epoch)`, `I = hash_to_G1(base_aad, "cbss/ibe/v1")`. Proxies compute the same partial `σ_i = s_i · I` and the chain runs the same pairing check `e(σ_i, G2_gen) == e(I, S_i)`. **The cryptographic verification path is byte-for-byte identical to the runner path** — only the authorization gate differs.

### 3.4 Proxy-side validation — operator branch (insert in §3.7)

> **§3.7.1 Operator-principal requests.** For a `SignedOperatorReleaseRequest`, the proxy runs the **operator checklist** below **instead of** the runner checklist's job/manifest rows (the grant replaces the dispatcher-assignment + manifest-entitlement + `SecretPolicy.actors` rows). All **crypto/committee/epoch/freshness/anti-replay** rows are unchanged.

| Check | Source of truth |
|---|---|
| `request_block ∈ [head − REQUEST_FRESHNESS_BLOCKS, head]` | proxy clock + chain head |
| `OperatorReleaseGrant[grant_id]` exists and is not revoked/expired at current head | `0x04` |
| `grant.secret_id == body.secret_id` and (`grant.version_pin` is `None` **or** `== body.version`) | `0x04` |
| `auth_sig` verifies `request_hash` against `grant.auth_pubkey` | `0x04` |
| **No dispatcher/job check. No manifest entitlement check. No `SecretPolicy.actors` check.** (grant subsumes all three) | — |
| If `grant.tee_required`, service has a live non-revoked grant-scoped attestation `tee_att_op:{grant_id}` (§6a) — NOT the runner `tee_att:{job_id}:{runner}`; fail-closed until §6a ships | `0x05` (TEE Verifier) |
| Anti-replay: `(release_id, proxy_id)` not previously served | proxy bloom (24h) + chain `release_receipt` |
| Per-grant rate limit: ≤ `grant.max_releases_per_hour` | proxy local |
| Proxy is a member of the referenced release key's `committee` at current head | `0x04` |
| `body.serve_epoch == release_key.committee_epoch` at current head (`EpochMismatch` otherwise) | `0x04` |
| `SecretVersion.pending == false` | `0x04` |

Failure codes: `OperatorGrantNotFound`, `OperatorGrantRevoked`, `OperatorGrantExpired`, `InvalidAuthSignature`, `OperatorGrantVersionMismatch`, `OperatorRateLimited`, plus the shared `StaleRequestBlock` / `EpochMismatch` / `SecretPending`.

### 3.5 Runner pull flow — operator variant (insert in §3.8)

> **§3.8.1 Operator standing pull flow.** Identical to §3.8 except **there is no dispatcher lookup and no runner-registry key** — the principal is the operator's standing service authenticating with `K_auth`:
>
> 1. Standing service needs `K_sign` to build a signature (e.g. a Cowboy tx in the CIP-34 demo).
> 2. Service resolves `secret_id = {owner, key_hash}` and the target `version` (grant `version_pin`, or latest non-pending), reads the release key snapshot + `committee_epoch`.
> 3. Service picks t of n proxies, generates a fresh `release_nonce`, assembles `OperatorReleaseRequestBody` with `request_block = head`, `serve_epoch = committee_epoch`, and signs it with `K_auth` → `SignedOperatorReleaseRequest`.
> 4. Sends to t of n proxies in parallel. Each proxy validates per §3.7.1, returns `σ_i`.
> 5. Service pairing-checks each `σ_i`, Lagrange-combines → `σ = MSK · I`, derives `K = HKDF(serialize(e(σ, U)), "cbss/ibe/v1" || aad)`, AES-GCM-decrypts `wrapped_dek` → DEK, fetches + decrypts the CBFS object → `K_sign`.
> 6. Service uses `K_sign` to produce the signature, then **zeroizes** `K_sign`, DEK, and σ partials.
> 7. Each participating proxy independently submits `SubmitReleaseReceipt` (operator variant). Payment flows proxy ← **owner account** (the grant's `secret_id.account`), capped at quorum t.
>
> **`tee_required` path:** steps 5–6 execute inside the enclave; `K_sign` never enters host memory (§1.2, §8.9).

### 3.6 `SubmitReleaseReceipt` — operator variant (insert in §3.5 SubmitReleaseReceipt)

`SubmitReleaseReceipt` (opcode 76) carries `SignedOperatorReleaseRequest` in the `runner_request`-analog slot (the codec enum arm). Chain validation differs from the runner path only in the **authorization** rows:

- Step 3 (sig): verify `auth_sig` against `grant.auth_pubkey` at current head (not the runner registry).
- Step 5 (authorization): verify `OperatorReleaseGrant[grant_id]` exists, not revoked/expired, `grant.secret_id == body.secret_id`, version consistent — **instead of** the actor/runner/job ACL check. Same current-head, revoked-within-window-rejects trade-off (§3.7).
- **Payment:** debit `RELEASE_FEE_PER_RECEIPT` from the **owner account** (`body.secret_id.account`); credit `proxy_id`. Overdraft/delinquency machinery is unchanged (an owner starving its own grant self-suspends its own releases — acceptable, since it is the owner's own secret).
- All other steps (request_hash recompute, recipient consistency, pairing check `e(σ_i, G2) == e(I, S_i)`, reshare-aware committee lookup, `release_id` dedup, quorum cap, `SecretReleased` at t-th receipt) are **byte-for-byte identical**.

`release_id` for dedup/quorum uses the operator derivation (§3.3). The `SecretReleased` event's actor/runner fields are `None`/`grant_id` on the operator variant.

---

## 4. Parameters (insert in §4)

| Parameter | Default | Meaning |
|---|---|---|
| `MAX_OPERATOR_RELEASES_PER_GRANT_PER_HOUR` | `governance-tunable` (e.g. 3600) | ceiling on `grant.max_releases_per_hour` |
| `MAX_OPERATOR_GRANTS_PER_ACCOUNT` | `governance-tunable` (e.g. 64) | per-account grant quota |
| `MAX_SERVICE_LABEL_BYTES` | `64` | bound on `service_label` |

Reuses (unchanged): `REQUEST_FRESHNESS_BLOCKS`, `PROXY_CACHE_TTL_BLOCKS`, `RELEASE_FEE_PER_RECEIPT`, `MAX_RELEASE_OVERDRAFT`, all committee/DKG/reshare params.

---

## 5. SDK / CLI surface (insert in §5)

There is **no actor manifest** on the operator path (the principal is an account, not a deployed actor), so the grant is issued by CLI/tx, not declared in a manifest entitlement. Proposed §5.6:

```bash
# Store the operator signing key as an ordinary secret (default path):
cowboy secrets set OPERATOR_SIGNING_KEY --from-file .cowboy/key   # SetSecret op68

# Generate a warm auth key (K_auth) for the standing service, separate from the account root key:
cowboy secrets operator-authkey new --out service/authkey.json

# Register the standing-service grant:
cowboy secrets grant-operator OPERATOR_SIGNING_KEY \
    --auth-pubkey $(jq -r .public service/authkey.json) \
    --max-releases-per-hour 3600 \
    [--tee-required] [--expiry-block N] [--version N]          # RegisterOperatorReleaseGrant op154

# Revoke (kill switch):
cowboy secrets revoke-operator-grant <grant_id>                # RevokeOperatorReleaseGrant op155
```

The standing service (e.g. `server.js`) links a small client that performs §3.8.1 with `service/authkey.json`. **Errors** (add to §5.3): `OperatorGrantNotFound`, `OperatorGrantRevoked`, `OperatorGrantExpired`, `InvalidAuthSignature`, `OperatorGrantVersionMismatch`, `OperatorRateLimited`, `OperatorGrantCrossAccount`.

---

## 6. Security considerations (insert §8.9)

> **§8.9 Operator-principal auth-key compromise.** The operator class adds a **standing** authorization path, distinct from the per-job runner path of §8.3. Its threat surface:
>
> - **`K_auth` compromise (warm key on the service).** An attacker with `K_auth` can pull the granted secret until `K_root` issues `RevokeOperatorReleaseGrant`. This is **narrower** than the status-quo plaintext-at-rest exposure (permanent, non-revocable, silent theft of `K_sign` from disk): the attacker gets a *revocable, audited* release capability, not the key file, and not account control (`K_auth ≠ K_root`, §2), and every pull leaves a `release_receipt` on chain. **But three sharp caveats (do not oversell revocability):**
>     - **Revocation has a full-release grace window (F5).** During `finality + max proxy cache TTL`, a compromised `K_auth` can still assemble a *complete* `t`-of-`n` release (§3.2) — the chain gates payment, not reconstruction.
>     - **One release = permanent key compromise.** `K_sign` is a long-lived signing key; a single release in the window compromises it forever. Revocation stops *future* releases only. The real incident response is to **rotate `K_sign`** (§3.2), and because `version_pin = None` auto-follows versions (§3.1, F4), rotation without revocation is a no-op against a live grant — **revoke AND rotate**.
> - **Transient reconstruction (inherent, §1.2).** On the non-TEE path, a host compromise *at signing time* observes the reconstructed `K_sign` in memory. The operator class does not claim to prevent this; `grant.tee_required` does (reconstruction in-enclave) — but only once the §6a `0x05` companion ships (F7). This is the same "requester sees the plaintext it is authorized to fetch" limit as §8.3.
> - **`K_root` compromise.** Same as §8.2: an attacker with the account root key can register an attacker-controlled grant (or `UpdateSecretPolicy`) and pull the secret. Account-key compromise remains the limit of the model, recovered out-of-band. The operator class's contribution is keeping `K_root` **cold/offline** — the warm service holds only `K_auth`. Note that **`UpdateSecretPolicy` lockdown does NOT cover grants (F4):** setting `SecretPolicy.actors = Some([])` as an emergency stop closes the *actor* door only; every live `OperatorReleaseGrant` stays serviceable. A complete lockdown must enumerate and `Revoke` all grants on the secret (or `DeleteSecret`).
> - **Rate limit is a cost/grief bound, not a key-exposure bound, and not on-chain (F6).** `grant.max_releases_per_hour` is **proxy-local, off-chain, advisory** — the chain never rate-limits `SubmitReleaseReceipt` billing in either path. It is amplifiable ~`n/t`× by fanning across different proxy subsets, and it does **not** bound key exposure (one release already compromises the key — see above). The only *hard, on-chain* economic bound is `MAX_RELEASE_OVERDRAFT` → `delinquent` status. **Two-edged:** §8.9's advice to set `max_releases_per_hour` to the service's real signing rate is also a **DoS lever** — a compromised `K_auth` burns the hourly budget, the honest service then hits `OperatorRateLimited` and cannot sign, and sustained abuse drives the owner to `ActorReleaseDebt`/`delinquent`, which (canonical §3.5) makes **`JobSubmit` reject account-wide** until refund + revoke. So warm-key compromise can escalate to "honest service bricked," bounded by the overdraft cap and same-account, but not costless. Detection surface is the per-receipt `release_receipt` trail + `SecretReleased` events; owners SHOULD monitor for anomalies and treat `OperatorRateLimited` bursts as a compromise signal.
>
> **Net:** the operator class converts "permanent, silent, non-revocable key theft" into "revocable, audited release capability" — a real improvement — but with (a) a bounded full-release grace window on revoke, (b) a long-lived key that must be *rotated*, not just revoked, after compromise, and (c) an availability failure mode (rate-limit/delinquency) under `K_auth` abuse. It does not make a network-exposed signing service unconditionally safe, and its strongest claim (transient-reconstruction elimination) is conditional on the §6a companion.

---

## 6a. Cross-repo companion — grant-scoped TEE attestation (`0x05` / CIP-23) — REQUIRED for `tee_required` (F7)

The `tee_required` path is the **only** mechanism that eliminates transient in-use reconstruction (§1.2, §8.9), so it is load-bearing — but it is **not** a free reuse of the runner TEE flow. The current `0x05` TEE Verifier (canonical CIP-24 §3.5 step 11, §9.5) binds attestations to a **registered runner and a `job_id`** in three concrete ways the operator path cannot satisfy:

1. Records are keyed `tee_att:{job_id_32}:{runner_20}`; the operator body has **no `job_id` and no `runner_id`**.
2. `TeeAttestationRecord { job_id, runner, ... }` and the canonical `cbss/tee-attestation/v1` payload are signed **over the job and runner**; a standing service is not a registered runner (§3.8.1) and its `K_auth` has no attestation-key registration path.
3. The receipt-time check (§3.6) reads `tee_att:{body.job_id}:{body.runner_id}` — fields the operator arm does not carry.

This amendment therefore **requires** a companion `0x05`/CIP-23 change (a separate stacked PR; this document specifies its shape so the dependency is explicit, not hand-waved):

**New record (grant-scoped).** Keyed `tee_att_op:{grant_id_32}`:

```
OperatorTeeAttestationRecord {
    grant_id:          GrantId
    service_pubkey:    PublicKey        // the standing service's attestation-signing key (registered; distinct from K_auth)
    tee_type:          TeeType          // SGX/TDX (P-256) | SEV-SNP (P-384), as in §9.5
    measurement_hash:  Bytes32
    attested_at_block: BlockHeight
    expires_at_block:  BlockHeight
    revoked:           bool
}
```

**New submission flow.** `SubmitOperatorTeeAttestation` (opcode provisional, next-free) — analog of `SubmitTeeAttestation`, but the verifier checks a registered ECDSA attestation key over a **new domain-separated payload** `cbss/operator-tee-attestation/v1` binding `(grant_id, service_pubkey, normalized tee_type, measurement_hash, expires_at_block, quote_bytes)` — NOT `(job_id, runner)`. The trust store reuses the existing `tee_key:{tee_type}:{measurement_hash_32}` companion (§3.2 of canonical CIP-24) unchanged.

**Receipt-time lookup (operator arm of §3.6).** When `SecretVersion.policy.tee_required` OR `grant.tee_required` is set, the chain reads `tee_att_op:{grant_id}` (not `tee_att:{job_id}:{runner}`), requires it non-revoked with `attested_at_block ≤ submission_block ≤ expires_at_block` and a `tee_type` consistent with the grant's expectation, else rejects with `SecretRequiresTEE`. `tee_attested` remains **chain-derived, never proxy-asserted** (as in canonical step 11). Proxy-side (§3.7.1) the `tee_required` row reads the same `tee_att_op:{grant_id}` record.

**Sequencing / fail-closed.** Until this companion ships, a `tee_required` grant is **non-serviceable**: proxies and the chain fail closed (`SecretRequiresTEE`), and the §1.2/§8.9 transient-reconstruction-elimination claim is **deferred**. The default (non-TEE) operator path is unaffected and shippable independently. An acceptable alternative to writing §6a now is to **remove `tee_required` from this amendment entirely** (drop the field + the elimination claim) and file it as a follow-up — but the field MUST NOT ship as an unbacked no-op.

---

## 7. Interaction with other CIPs / use cases (insert §9.7)

> **§9.7 Operator-signing services (CIP-34 demo and beyond).** The operator-principal class is the CBSS surface for **standing off-chain services that sign with a long-lived key** — the CIP-34 chat demo's operator/deployer (`server.js`, which today holds `.cowboy/key` in plaintext), bridge relayers holding an EVM key, and services plumbing an LLM-provider key. Such a service is not a dispatched runner and not a deployed actor, so §3.7/§3.8 could not authorize it; §3.7.1/§3.8.1 do. The class composes with CIP-23 (`tee_required`) for enclave-bound reconstruction **via the required §6a `0x05` companion** (a grant-scoped attestation record — a genuine cross-repo dependency, not a reuse of the runner TEE flow) and with CIP-9 (the `K_sign` ciphertext rides an ordinary private volume / CBFS object). It does **not** interact with CIP-34 settlement or the §3.4.6 tlock path — those remain job/auction-scoped; the operator class is orthogonal (account-scoped standing release).

---

## 8. Corrections/supplements this amendment implies for the CURRENT CIP-24

Beyond the additive class, the analysis surfaced places where the **current** spec over-specifies "runner" as the sole confidential-release principal. These are the edits the amendment requires (all backward-compatible — the runner path is unchanged; the operator path is a second arm):

1. **§3.5 `ReleaseRequestBody`** hard-codes `actor` / `runner_id` / `job_id`. → Generalize to a `Principal` enum `{ Runner{actor,runner_id,job_id}, Operator{grant_id} }`; `release_id` derivation branches on the arm (§3.3).
2. **§3.7 checklist** presents dispatcher-assignment + manifest-entitlement + `SecretPolicy.actors` as **mandatory** rows. → They are mandatory **for the runner arm**; the operator arm substitutes the grant rows (§3.4 / §3.7.1). Add the §3.7.1 subsection.
3. **§3.8 pull flow** narrates "Runner R" as the only principal and reads the dispatcher. → Add §3.8.1 (no dispatcher, `K_auth` in place of the runner-registry key).
4. **`SubmitReleaseReceipt` (§3.5)** step 3 (runner-registry sig) and step 5 (actor/runner/job ACL) assume the runner arm. → Add the operator-arm validation + owner-account payment (§3.6).
5. **§5 (SDK)** assumes the principal is a **deployed actor** declaring `secrets.read`/`secrets.verify` in a CIP-6 manifest. → The operator path has no manifest; add the §5.6 CLI/grant surface. Note that the operator grant is the account-scoped analog of a manifest entitlement.
6. **§8 (Security)** has no standing-authorization threat model (§8.3 is per-job). → Add §8.9.
7. **§3.1** — add `OperatorReleaseGrant`; **§3.3** — add opcodes 154/155 (provisional); **§4** — add the three params; **History** — add the 2026-07-06 entry.
8. **§3.5 `Principal` enum (M1)** — the arm discriminant MUST be a **normative, leading, authenticated 1-byte tag** inside the signed body; the signature-domain string and the verify-key source are selected from that authenticated tag, not from an untrusted outer codec framing. Applies to **both** arms (runner + operator).
9. **§3.5 `release_id` (L1)** — prepend a 1-byte principal-domain to **both** derivations (`0x00` runner, `0x01` operator) as defense-in-depth against future field-width changes; keccak256 already prevents collision today but the shared dedup/quorum namespace warrants an explicit arm tag.
10. **§9.5 / `0x05` TEE Verifier (F7)** — the `tee_required` operator path REQUIRES the new grant-scoped attestation contract of **§6a** (`tee_att_op:{grant_id}`, `SubmitOperatorTeeAttestation`, `cbss/operator-tee-attestation/v1` payload). This is a stacked CIP-23/`0x05` companion PR, NOT a reuse of the runner `tee_att:{job_id}:{runner}` schema.

Items 1–7 touch only the authorization layer and no cryptography. Item 10 (the TEE companion) is a **cross-repo** change (`0x05` schema + a new attestation submission), which is why the default (non-TEE) operator path is the shippable core and `tee_required` is gated behind §6a. None of these touches §3.4 cryptography, the DKG/reshare ceremonies (§3.6), the tlock mode (§3.4.6), the envelope format (`WrappedDek` v2), or the identity/AAD derivation.

---

## 9. Proposed History entry

> 2026-07-06: **v1 amendment (DRAFT) — operator-principal release class (§3.4.7 / §3.7.1 / §3.8.1 / §8.9).** Adds a third release mode: **confidential**, **account-authorized**, **standing** release for off-chain operator services that sign with a long-lived key (canonical instance: the CIP-34 demo operator/deployer, which today holds `.cowboy/key` in plaintext). Stays in the `cbss/ibe/v1` identity space (unlike tlock's `cbss/tlock/v1`) because the released key is secret — **no new key, DKG, domain, or trust**; only the authorization gate changes (an on-chain `OperatorReleaseGrant` + `K_auth` signature replace the dispatcher-assignment + manifest-entitlement + `SecretPolicy.actors` triple). Introduces `RegisterOperatorReleaseGrant` (op154, provisional), `RevokeOperatorReleaseGrant` (op155), the `OperatorReleaseRequestBody` principal arm, §4 `MAX_OPERATOR_*` params, and the §8.9 standing-auth threat model. Custody eliminates plaintext-at-rest and adds revocability/threshold-gating/audit; it does **not** eliminate transient in-use reconstruction unless `tee_required`, which itself requires the **§6a grant-scoped `0x05` attestation companion** (a cross-repo dependency — the default non-TEE path is the shippable core). Revocation is a **future-release cut-off with a bounded full-release grace window** (finality + max proxy cache TTL), not a retroactive seal; a compromised `K_auth` is remediated by **rotating `K_sign` AND revoking**, not revoke alone. The `Principal` enum discriminant is normative + authenticated (M1); `release_id` gains a principal-domain byte (L1). Companion evaluation: `refs/analysis/2026-07-06-cbss-operator-signing-evaluation.md` (Model A). Reference implementation: TBD.

---

## Appendix — anchors into current CIP-24 (revision of 2026-07-03)

| Insert point | Current anchor |
|---|---|
| `OperatorReleaseGrant` struct | §3.1, after `SecretReleaseKey` (L167–184) |
| `SecretPolicy` (compared) | §3.1 L136–147 |
| opcodes 154/155 | §3.3 allocation table L271–292 |
| identity `I` / `base_aad` (reused unchanged) | §3.5 L796–802; §3.4.3 |
| `ReleaseRequestBody` / `release_id` (generalized) | §3.5 L735–759 |
| domain-separated sig payloads (add `auth_sig`) | §3.5 L761–794 |
| `SubmitReleaseReceipt` (operator arm) | §3.5 L720–828 |
| §3.7 checklist (add §3.7.1) | §3.7 L1013–1035 |
| §3.8 pull flow (add §3.8.1) | §3.8 L1037–1071 |
| §5.1 entitlement (contrast; add §5.6 CLI) | §5.1 L1214–1242; §5.4 CLI |
| §8.2 owner-key compromise (referenced by §8.9) | §8 L1498–1509 |
| §9.5 CIP-23 `tee_required` (NOT reused — requires §6a `0x05` companion) | §9.5 L1589–1591; §3.5 step 11 L824 |
| History entry | after L1611 |
