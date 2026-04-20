---
title: "CIP-16: Custom Domains and First-Party TLDs"
description: Extend DNS-addressable actors with protocol-owned `.cow` / `.cowboy` names and externally attached domains verified through DNS
icon: globe
---

<Note>
  **Status:** Draft
  **Type:** Standards Track
  **Category:** Core
  **Created:** 2026-03-08
  **Requires:** CIP-14 (DNS-Addressable Actors), CIP-2 (Off-Chain Compute), CIP-3 (Dual-Metered Gas), CIP-5 (Timers)
</Note>

## 1. Abstract

This proposal extends **DNS-Addressable Actors** (CIP-14) with two additional naming modes:

- **First-party TLD names** under protocol-controlled zones such as `.cow` and `.cowboy`
- **External custom domains** such as `api.example.com`, attached to an actor through DNS-based verification

This CIP specifies:

- How the existing Route Registry is extended to manage domain classes beyond `*.cowboy.network`
- Registration and renewal rules for first-party TLD labels (for example, `alice.cow`)
- DNS-based control verification for externally attached domains
- Canonical DNS and TLS onboarding flows for external domains
- Periodic reverification and suspension rules for externally attached domains
- Resolution precedence and compatibility with CIP-14 routing semantics

This CIP assumes the Cowboy protocol or its operating entity controls the authoritative DNS and registrar workflow for the first-party TLDs `.cow` and/or `.cowboy`. The business and ICANN mechanics of obtaining and operating those TLDs are outside protocol scope; this CIP defines only the protocol behavior once that control exists.

---

## 2. Motivation

CIP-14 deliberately launched with a subdomain-first model under `cowboy.network` to keep ingress simple. That is the right v1 for internet-addressable actors, but it leaves two important gaps:

1. **Native protocol naming**: If Cowboy controls `.cow` or `.cowboy`, actors should be reachable at second-level names like `alice.cow` rather than only at `alice.cowboy.network`.
2. **Brand and migration support**: Teams and users already own DNS names such as `app.example.com`. They should be able to attach those domains to actors without forcing users into a Cowboy-only namespace.

The protocol should support both without fragmenting routing. From the user's perspective, whether the request arrives at `alice.cow`, `alice.cowboy`, `alice.cowboy.network`, or `api.example.com`, the result should be the same: the Gateway resolves a verified route and dispatches to the actor defined by the Route Registry.

---

## 3. Design Goals

- Extend CIP-14 without changing its query/command execution model
- Preserve ordinary DNS and browser compatibility; no alternative roots
- Use a single authoritative on-chain registry model for all actor-bound names
- Make external-domain attachment verifiable and revocable through DNS state
- Separate **protocol-owned namespace registration** from **external-domain attachment**
- Keep wildcard and advanced delegation out of v1 unless required
- Make periodic reverification explicit so stale or hijacked external domains do not remain bound indefinitely

## 4. Non-goals

- Defining the legal or registrar-business process for obtaining `.cow` or `.cowboy`
- Tokenizing domains as transferable RWAs or DeFi assets
- Supporting wildcard external domains in v1
- Supporting arbitrary alternative DNS roots or Handshake-style name resolution
- Defining static asset serving; that remains follow-on work on top of CIP-9 public volumes
- Defining payment gating or stream bridging; those remain follow-on CIPs

---

## 5. Definitions

- **First-party TLD**: A DNS zone operated by Cowboy at the registry/authoritative-DNS level, such as `.cow` or `.cowboy`
- **Second-level label**: The label registered directly under a first-party TLD, such as `alice` in `alice.cow`
- **External domain**: A domain or subdomain not under a Cowboy-controlled TLD, such as `api.example.com`
- **Domain attachment**: Binding an external domain to an actor after proving control of the DNS name
- **Verification challenge**: A protocol-generated token that must appear in DNS to prove external-domain control
- **Canonical edge target**: The hostname or DNS target to which external domains point for Cowboy Gateway ingress
- **Suspended binding**: A domain binding that remains recorded on-chain but is not served because verification or DNS requirements are no longer satisfied

---

## 6. Domain Classes

### 6.1 First-Party TLD Names

When Cowboy controls `.cow` and/or `.cowboy`, the Route Registry becomes the authoritative registration source for second-level labels:

```
alice.cow
alice.cowboy
```

Once a label is registered, it owns its subtree under that TLD:

```
api.alice.cow
docs.alice.cow
app.alice.cowboy
```

Subdomain behavior follows the same `subdomain_policy` model introduced in CIP-14.

### 6.2 External Custom Domains

External domains are attached, not minted. In v1, this CIP supports **exact FQDN attachment** only:

```
api.example.com
chat.example.org
www.brand.net
```

Wildcard external attachment (for example `*.example.com`) is deferred.

### 6.3 Compatibility With `cowboy.network`

The existing `*.cowboy.network` namespace from CIP-14 remains fully valid. This CIP adds new namespace classes; it does not replace the original one.

---

## 7. Route Registry Extension

This CIP extends the existing Route Registry system actor from CIP-14 rather than creating a second naming registry.

### 7.1 Extended Binding Record

The Route Registry record is generalized as:

```
DomainBinding {
  fqdn:                string,        // normalized ASCII/punycode
  actor_address:       Address,
  owner:               Address,
  namespace_kind:      u8,            // 0 = COWBOY_NETWORK, 1 = FIRST_PARTY_TLD, 2 = EXTERNAL
  tld_kind:            u8?,           // 0 = cowboy.network zone, 1 = .cow, 2 = .cowboy, null for EXTERNAL
  status:              u8,            // 0 = ACTIVE, 1 = PENDING, 2 = SUSPENDED, 3 = EXPIRED, 4 = DETACHED
  subdomain_policy:    u8,            // same model as CIP-14
  registered_at:       BlockHeight,
  expires_at:          BlockHeight?,  // required for protocol-owned namespaces; optional for external attachments
  verified_at:         BlockHeight?,  // external domains only
  next_reverify_at:    BlockHeight?,  // external domains only
  dns_target:          string?,       // required for EXTERNAL: canonical edge target
  verification_nonce:  bytes32?,      // external domains only while PENDING or ACTIVE
  verification_method: u8?            // 0 = NONE, 1 = TXT_CHALLENGE
}
```

### 7.2 Normalization Rules

- All FQDNs MUST be normalized to lowercase ASCII punycode before storage
- Trailing dots MUST be removed before normalization
- Unicode input MUST be rejected unless it round-trips to a valid ASCII punycode name
- Comparisons are exact after normalization

### 7.3 Resolution Precedence

Resolution is exact-FQDN first:

1. exact external binding
2. exact first-party TLD binding
3. exact `cowboy.network` binding
4. parent subtree handling via `subdomain_policy`

There is no cross-namespace shadowing because the full normalized FQDN is the lookup key.

---

## 8. First-Party TLD Registration

### 8.1 Supported TLDs

This CIP defines protocol behavior for the following first-party zones:

- `.cow`
- `.cowboy`

Governance MAY enable either or both. A deployment that controls only one TLD simply disables the other.

### 8.2 Registration

The Route Registry exposes:

| Method | Args | Returns | Description |
|--------|------|---------|-------------|
| `register_tld_label` | `tld_kind`, `label`, `actor_address`, `duration_blocks` | `DomainBinding` | Register a second-level label under `.cow` or `.cowboy` |
| `renew_tld_label` | `fqdn`, `duration_blocks` | `DomainBinding` | Renew an existing label |
| `transfer_tld_label` | `fqdn`, `new_owner` | `DomainBinding` | Transfer label ownership |
| `set_actor` | `fqdn`, `actor_address` | `DomainBinding` | Re-point a name to another actor |

**Requirements:**

1. The target actor holds `ingress.http`
2. The label is available or has expired past grace/auction
3. Registration fee is paid in `CBY`
4. The caller is the actor or its controlling owner account

### 8.3 Economics

First-party TLD names use the same scarcity model as CIP-14 names:

- shorter labels pay higher annual fees
- renewals extend from current expiry
- expired labels enter a grace period followed by a release auction

Governance MAY price `.cow` and `.cowboy` independently.

### 8.4 Reserved Labels

Governance reserves protocol-critical labels such as:

- `www`
- `api`
- `dns`
- `gateway`
- `relay`
- `node`
- `admin`
- `system`

Reserved-label policy applies independently per TLD.

---

## 9. External Domain Attachment

### 9.1 Overview

An external domain is attached in three phases:

1. **Begin attachment** on-chain
2. **Prove control** through DNS
3. **Activate binding** after off-chain verification and certificate readiness

### 9.2 Attachment API

The Route Registry exposes:

| Method | Args | Returns | Description |
|--------|------|---------|-------------|
| `begin_attach_external` | `fqdn`, `actor_address` | `DomainBinding` | Create a pending external-domain attachment and challenge |
| `complete_attach_external` | `fqdn`, `verification_attestation` | `DomainBinding` | System-only callback that activates a verified domain |
| `reverify_external` | `fqdn` | `void` | Trigger a re-verification flow |
| `detach_external` | `fqdn` | `void` | Remove a binding |
| `suspend_external` | `fqdn`, `reason` | `void` | System-only: suspend a failing binding |

**Requirements for `begin_attach_external`:**

1. The normalized `fqdn` is not under a Cowboy-controlled namespace (`*.cowboy.network`, `.cow`, or `.cowboy`)
2. The target actor holds `ingress.http`
3. The caller is the actor or its controlling owner account
4. The exact normalized `fqdn` does not already have an `ACTIVE`, `PENDING`, or `SUSPENDED` binding
5. `fqdn` is an exact host name, not a wildcard pattern

### 9.3 DNS Control Proof (v1)

The v1 verification method is **TXT challenge**.

When `begin_attach_external(fqdn, actor_address)` is called, the Route Registry generates:

```
verification_nonce = random_bytes32()
challenge_value = "cowboy:v1:" || chain_id || ":" || fqdn || ":" || actor_address || ":" || verification_nonce
```

The owner MUST publish:

```
_cowboy-challenge.<fqdn> TXT "<challenge_value>"
```

The challenge is valid until `CHALLENGE_EXPIRY_BLOCKS` after `begin_attach_external`.

### 9.4 Canonical Edge Target

In addition to the TXT challenge, the external domain MUST point to the Cowboy edge.

For v1:

- subdomains MUST use `CNAME` to the canonical edge hostname
- apex domains MAY use `ALIAS`/`ANAME` or equivalent flattening if the DNS provider supports it

The canonical edge hostname is governance-configured:

```
CANONICAL_EDGE_HOSTNAME = edge.cowboy.network
```

Future deployments MAY switch this to a first-party TLD host once `.cow` or `.cowboy` is live.

### 9.5 TLS Onboarding

External domains in v1 use **gateway-managed TLS** with delegated DNS-01:

The owner MUST publish:

```
_acme-challenge.<fqdn> CNAME <token>.acme.cowboy.network
```

This allows the Gateway control plane to obtain and renew certificates without requiring the actor owner to operate their own ACME client.

Bring-your-own certificate mode is deferred.

### 9.6 Verification Execution

External verification uses CIP-2 off-chain jobs:

1. `begin_attach_external` emits `ExternalDomainVerificationRequested`
2. The protocol dispatches a verification task to multiple verifiers
3. Verifiers confirm:
   - the TXT challenge matches exactly
   - the domain points at the canonical edge target
   - ACME delegation exists
4. A verifier callback invokes `complete_attach_external`
5. The binding becomes `ACTIVE` only after verification succeeds

### 9.7 Status Transitions

```
PENDING -> ACTIVE      // challenge verified
PENDING -> EXPIRED     // challenge window elapsed
PENDING -> DETACHED    // owner cancels before activation
ACTIVE  -> SUSPENDED   // reverification failed or edge target removed
SUSPENDED -> ACTIVE    // reverification succeeds
ACTIVE  -> DETACHED    // owner detaches
SUSPENDED -> DETACHED  // owner detaches
```

### 9.8 Reverification

External domains MUST be reverified periodically.

- `next_reverify_at` is set when activation succeeds
- a CIP-5 timer triggers reverification every `EXTERNAL_REVERIFY_INTERVAL`
- if TXT proof, edge target, or ACME delegation is missing at reverification time, the binding becomes `SUSPENDED`

Suspended bindings remain on-chain for auditability but MUST NOT be served by Gateways.
Detached bindings are excluded from resolution immediately and MAY be reattached later by creating a fresh pending record.

---

## 10. Gateway Behavior

### 10.1 Resolution

Gateways resolve incoming hostnames by querying the Route Registry with the fully normalized FQDN.

For an external domain, the Gateway MUST confirm:

- binding status is `ACTIVE`
- the binding is not past `next_reverify_at`
- TLS certificate is present and valid

### 10.2 Serving Policy

If an external binding is `PENDING`, `SUSPENDED`, `EXPIRED`, or `DETACHED`, Gateways MUST NOT dispatch to the actor.

Recommended responses:

- `PENDING`: `503 Service Unavailable`
- `SUSPENDED`: `421 Misdirected Request` or `503 Service Unavailable`
- `EXPIRED`: `404 Not Found`
- `DETACHED`: `404 Not Found`

### 10.3 First-Party TLD DNS

For `.cow` and `.cowboy`, the Cowboy-controlled DNS authority serves records directly from the Route Registry namespace. No TXT proof or external ACME delegation is required for first-party TLD labels.

---

## 11. Security Considerations

### 11.1 Domain Hijack and Stale Control

External-domain control can change off-chain without any on-chain transaction. Periodic reverification is mandatory to reduce stale bindings.

### 11.2 DNS Normalization

All domain comparisons use normalized punycode ASCII. Gateways and the Route Registry MUST reject mismatched or non-normalized names.

### 11.3 Certificate Issuance Abuse

Gateways MUST NOT attempt certificate issuance for an external domain until:

- TXT challenge is valid
- edge target is correct
- ACME delegation is present
- the Route Registry status is `PENDING` for the same nonce

### 11.4 External DNS Target Drift

If an external domain stops pointing at the Cowboy edge, the binding becomes suspended at the next verification cycle. Gateways MUST NOT continue serving stale attachments indefinitely.

### 11.5 Official TLD Concentration Risk

First-party TLD operation introduces operational trust in the entity or governance process controlling `.cow` / `.cowboy`. This is unavoidable for ICANN-root DNS and is a known centralization point outside the consensus protocol.

---

## 12. Protocol Constants

```
// Namespace kinds
NAMESPACE_COWBOY_NETWORK         = 0
NAMESPACE_FIRST_PARTY_TLD        = 1
NAMESPACE_EXTERNAL               = 2

// First-party TLD kinds
TLD_COW                          = 1
TLD_COWBOY                       = 2

// External verification
CHALLENGE_EXPIRY_BLOCKS          = 43_200        // ~12 hours at 1s block time
EXTERNAL_REVERIFY_INTERVAL       = 2_592_000     // ~30 days
CANONICAL_EDGE_HOSTNAME          = "edge.cowboy.network"
ACME_DELEGATION_ZONE             = "acme.cowboy.network"
```

---

## 13. Future Work

The following are explicitly deferred:

- wildcard external domain attachment
- DNSSEC-native verification path
- delegated registrars or reseller model for `.cow` / `.cowboy`
- bring-your-own certificates
- domain tokenization / marketplace mechanics
- unified public asset hosting manifests across CIP-9 and CIP-14

---

## 14. Backwards Compatibility

This CIP is additive to CIP-14:

- Existing `*.cowboy.network` names remain valid and unchanged
- Existing Route Registry records remain valid
- Gateways that do not implement CIP-16 simply cannot serve first-party TLD or external attached domains
- No changes are required to the query/command routing model from CIP-14

---

## 15. Rationale

### 15.1 Why Reuse the Route Registry

The route decision is the same regardless of namespace: resolve normalized FQDN to actor and dispatch through the CIP-14 ingress path. Splitting naming across multiple registries would create ambiguous authority and duplicate lifecycle logic.

### 15.2 Why TXT Challenge in v1

TXT-based proof is operationally simple, widely supported, and already familiar from certificate issuance flows. It is not fully trustless, but it fits Cowboy's off-chain verification model and keeps the first custom-domain release practical.

### 15.3 Why Exact External FQDNs Only

Wildcard attachments dramatically increase risk and verification complexity. Exact-FQDN attachment is enough for most APIs and websites, and leaves room for a future wildcard CIP once the Gateway and verification planes are battle-tested.

### 15.4 Why Assume `.cow` / `.cowboy`

If Cowboy controls the TLD, there is no reason to force all protocol-native names under `cowboy.network` forever. Supporting second-level labels under `.cow` / `.cowboy` is the natural extension of CIP-14's naming model.
