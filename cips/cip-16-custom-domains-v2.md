---
title: "CIP-16: Custom Domains and First-Party TLDs (v2)"
description: Code-aligned v2 — MajorityVote DNS verification, system-mediated callback, explicit migration, fee-charged reverification, corrected status codes, verified-fqdn injection
---

# CIP-16 v2

> **Versioning.** This is v2 of CIP-16. v1 is the canonical document `cip-16-custom-domains.md` (preserved verbatim as Part I). v2 = v1 + the alignment revision (Part II) + the cross-cutting conventions (Part III).
>
> **Conflict rule:** Part II is canonical wherever it contradicts Part I.
>
> **Summary of v2 changes**
>
> - **`VerificationMode::MajorityVote` for DNS verification** (not `Deterministic`). v1 §9.6 chose Deterministic, which requires byte-identical output + TEE — wrong for non-deterministic DNS. MajorityVote is already implemented (`runner/src/types.rs:215`).
> - **Two new `VerifierCheck` variants** — `DnsTxtRecordMatch` and `DnsCnameMatch` (per CIP-2 v2 Part II §2). Each runner queries `min_resolvers` independent recursive resolvers.
> - **Explicit `RouteRegistration → DomainBinding` migration rule** with field defaults for legacy CIP-14 records.
> - **`complete_attach_external` enforced at protocol layer.** New `SystemInstruction::ExternalDomainCallback` allowlisted to `RESULT_VERIFIER=0x03`.
> - **`EXTERNAL_REVERIFY_FEE`** charged from binding owner each reverify firing; insufficient balance → `SUSPENDED`.
> - **`verified_fqdn` injected into `HttpRequestEnvelope`** by `GatewayRegistry`. Actors trust this rather than the attacker-controllable `host` header.
> - **HTTP status codes corrected** — `SUSPENDED` → `503` (not `421 Misdirected Request`).
> - **`CANONICAL_EDGE_HOSTNAME` mode made explicit** — anycast (default) or SRV (optional).
> - **Centralization risks enumerated** — ACME control plane, anycast edge, first-party TLD authority, governance-pinned DNS verifier executor.

---

## Part I — v1 Specification (verbatim from `cip-16-custom-domains.md`)


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

---

## Part II — v2 Revision (canonical; verbatim from former `cip-16-aligned.md`)


<Note>
  **Status:** Draft (alignment revision; non-modifying companion to `cip-16-custom-domains.md`)
  **Type:** Standards Track
  **Category:** Core
  **Created:** 2026-04-21
  **Companion to:** `cip-16-custom-domains.md`
  **Reads with:** Part III of this document, `cip-14-dns-addressable-actors-v2.md` (Part II)
</Note>

## 0. What this document is

A code-aligned revision of CIP-16. The original specifies external-domain verification via "CIP-2 multi-verifier consensus" but reuses `VerificationMode::Deterministic` (which requires byte-identical output and TEE — wrong for non-deterministic DNS resolution). It leaves `complete_attach_external` as "system-only" without spelling out which system actor enforces the rule. It silently replaces CIP-14's `RouteRegistration` schema. It treats `CANONICAL_EDGE_HOSTNAME` as a single hostname without addressing multi-Gateway deployments. It chooses HTTP `421 Misdirected Request` for SUSPENDED bindings (which invites the wrong client behavior). And it leaves external-domain reverification fees unspecified, externalizing verifier compute cost onto the protocol indefinitely.

This document picks concrete answers for each.

---

## 1. Preconditions

| Amendment | Source | Description |
|-----------|--------|-------------|
| §2.3 | Part III of this document | Add `dns.attach_external` to entitlement registry |
| AMEND 2-A | Part III of this document §8 | Add `VerifierCheck::DnsTxtRecordMatch` variant |
| AMEND 2-B | Part III of this document §8 | Add `VerifierCheck::DnsCnameMatch` variant |
| §4 | `cip-14-dns-addressable-actors-v2.md` (Part II) | Route Registry exists at `0x0C` with the schema in §3 below |

---

## 2. Scope

Same as original §1: protocol-owned `.cow` / `.cowboy` second-level labels and externally attached FQDNs (exact-match in v1; wildcards deferred). Execution model is unchanged from CIP-14-aligned (read-handler RPC + system-mediated dispatch).

---

## 3. Route Registry record (extends CIP-14-aligned §4.1)

The original CIP-16 §7.1 silently replaced CIP-14's `RouteRegistration`. CIP-16-aligned makes the migration explicit and enumerates default values for legacy records.

```
DomainBinding {
  // shared with CIP-14-aligned RouteRegistration
  fqdn:                string,
  actor_address:       Address,
  owner:               Address,
  registered_at:       BlockHeight,
  expires_at:          BlockHeight?,        // null only for external bindings (see §5.8)
  subdomain_policy:    u8,
  // new in CIP-16-aligned
  namespace_kind:      u8,                  // 0 = COWBOY_NETWORK, 1 = FIRST_PARTY_TLD, 2 = EXTERNAL
  tld_kind:            u8?,                 // 0 = .cowboy.network, 1 = .cow, 2 = .cowboy, null for EXTERNAL
  status:              u8,                  // 0 = ACTIVE, 1 = PENDING, 2 = SUSPENDED, 3 = EXPIRED, 4 = DETACHED
  verified_at:         BlockHeight?,        // EXTERNAL only
  next_reverify_at:    BlockHeight?,        // EXTERNAL only
  dns_target:          string?,             // EXTERNAL only
  verification_nonce:  bytes32?,            // EXTERNAL only, set during PENDING
  verification_method: u8?                  // 0 = NONE, 1 = TXT_CHALLENGE
}
```

### 3.1 Migration from CIP-14-aligned (one-time at upgrade boundary)

Existing `RouteRegistration` records become `DomainBinding` with these defaults:

| Field | Default for legacy records |
|---|---|
| `namespace_kind` | `0 = COWBOY_NETWORK` |
| `tld_kind` | `0 = .cowboy.network` |
| `status` | `0 = ACTIVE` |
| `verified_at` | `null` |
| `next_reverify_at` | `null` |
| `dns_target` | `null` |
| `verification_nonce` | `null` |
| `verification_method` | `0 = NONE` |

`fqdn` is computed from the existing `name` field as `name || ".cowboy.network"`. No records are deleted or moved. Migration runs once at the protocol upgrade boundary (system actor at `0x0C` reads its own state and writes back the augmented schema in a single block).

### 3.2 Resolution precedence

Exact normalized FQDN lookup. The original §7.3 ranking ("exact external > first-party TLD > cowboy.network") is dropped because namespaces are disjoint — an external `api.example.com` cannot collide with a `cowboy.network` subdomain. One key, one lookup.

### 3.3 Normalization rules

Unchanged from original §7.2 (lowercase ASCII punycode, trailing dots stripped, exact comparison).

---

## 4. First-party TLD registration

Same as original §8 except:

- Method names match CIP-14-aligned style: `register_tld_label`, `renew_tld_label`, `transfer_tld_label`, `set_actor`.
- Fee splits route through `system:registry_settlement_config` (Part III of this document §6) — same configuration the `cowboy.network` registrations use, optionally with TLD-specific overrides via `target_pool: REGISTRY_TLD_<COW|COWBOY>` discriminants.
- Reserved labels (`www`, `api`, `dns`, `gateway`, `relay`, `node`, `admin`, `system`) apply per-TLD, governance-managed.

---

## 5. External domain attachment

### 5.1 Three-phase flow

Same shape as original §9.1: begin → prove → activate. Implementation differences below.

### 5.2 `begin_attach_external`

Caller authorization: caller is the actor itself, the actor's deployer, or an account holding `dns.attach_external` delegated by the actor's owner.

Generates `verification_nonce`, sets `status = PENDING`, computes the challenge value:

```
challenge_value = "cowboy:v1:" || hex(chain_id) || ":" || fqdn || ":" || hex(actor_address) || ":" || hex(verification_nonce)
```

Owner publishes:

```
_cowboy-challenge.<fqdn>  TXT    "<challenge_value>"
<fqdn>                     CNAME  edge.cowboy.network              // see §5.4
_acme-challenge.<fqdn>     CNAME  <token>.acme.cowboy.network      // see §5.5
```

The challenge is valid until `current_block + CHALLENGE_EXPIRY_BLOCKS = 43_200` (~12 hours).

### 5.3 Verification job (uses real CIP-2 primitives — corrects original §9.6)

`begin_attach_external` enqueues a `JobSpec` (`runner/src/types.rs:101`) into `JOB_DISPATCHER=0x02`:

```
JobSpec {
  job_type: JobType::Custom {
    executor_hash: DNS_VERIFIER_EXECUTOR_HASH,
    params:        serialize({fqdn, expected_challenge, expected_cname_target}),
  },
  verification: VerificationConfig {
    mode:                    VerificationMode::MajorityVote,         // not Deterministic
    runners:                 3,                                       // odd N for clean majority
    threshold:               2,                                       // ⌈N/2⌉
    checks:                  [
      VerifierCheck::DnsTxtRecordMatch {
        fqdn:           "_cowboy-challenge." || fqdn,
        expected_value: challenge_value,
        min_resolvers:  3,
      },
      VerifierCheck::DnsCnameMatch {
        fqdn:            fqdn,
        expected_target: CANONICAL_EDGE_HOSTNAME,
        min_resolvers:   3,
      },
    ],
    tee_required:            false,
    dispute_window_blocks:   75,
  },
  callback: CallbackInfo {
    actor:           ROUTE_REGISTRY,                                  // 0x0C
    handler:         "_dns.callback",
    payload:         None,
    correlation_id:  hex(verification_nonce),
    context:         serialize({fqdn, actor_address}),
  },
  ...
}
```

Each runner queries `min_resolvers` independent recursive resolvers (operator-configured public list — e.g. Google, Cloudflare, Quad9, OpenDNS) and reports per-resolver match/mismatch. The Result Verifier (`0x03`) aggregates with `MajorityVote` semantics.

DNS variability (TTL, anycast routing, edge caching) is absorbed by majority voting; minority disagreement does not trigger slashing unless it falls outside `dispute_window_blocks`.

The original CIP-16 §9.6 chooses `VerificationMode::Deterministic`, which (per `node/runner/src/types.rs:217` and CLAUDE.md) requires TEE + byte-identical comparison. DNS resolution is not byte-identical — different resolvers see different cached views. `MajorityVote` is the structurally correct mode and is already implemented (`runner/src/types.rs:215`).

### 5.4 Canonical edge target (anycast, with optional SRV)

The original §9.4 prescribes `CNAME → edge.cowboy.network` and assumes that hostname is anycast. CIP-16-aligned makes the assumption explicit:

- **Anycast mode** (default): `edge.cowboy.network` is a BGP-anycast A/AAAA record. CNAME target equals `edge.cowboy.network`. Browser-compatible without changes.
- **SRV mode** (optional): `edge.cowboy.network` is also published as an SRV record listing active Gateway endpoints (port + priority + weight). Useful for non-browser clients (CLIs, libraries) that respect SRV. Browsers do not query SRV for HTTPS today.

Default is anycast. The `DnsCnameMatch` check uses `CANONICAL_EDGE_HOSTNAME` as the expected target either way.

### 5.5 TLS / ACME delegation

Same as original §9.5 (DNS-01 via `_acme-challenge.<fqdn> CNAME → <token>.acme.cowboy.network`). The Cowboy ACME control plane obtains and renews certificates server-side. CIP-16-aligned adds explicit centralization risks to §10 below.

### 5.6 `complete_attach_external` (system-mediated — corrects original §9.2)

Replaces the original "system-only callback" hand-wave with an enforceable rule.

Implementation:

- A new `SystemInstruction::ExternalDomainCallback { fqdn, runner_consensus, attestation }` (opcode **67** per the canonical master allocation table in CIP-13 v2 §1).
- Sender allowlist: only `RESULT_VERIFIER=0x03`. The verifier's normal callback path emits this opcode after `MajorityVote` aggregation succeeds.
- The dispatcher routes the opcode to `ROUTE_REGISTRY.complete_attach_external_internal(fqdn, attestation)`.
- The Route Registry verifies `attestation.verification_nonce` matches the PENDING record, then:
  - `status = ACTIVE`
  - `verified_at = current_block`
  - `next_reverify_at = current_block + EXTERNAL_REVERIFY_INTERVAL`
  - schedules a CIP-5 timer at `next_reverify_at` to fire `_reverify_external(fqdn)`.

Failure paths:

- Verifier job returns `JobStatus::Failed` (`runner/src/types.rs:294`) → dispatcher emits `SuspendBinding{fqdn, reason}` opcode, sender allowlist still `0x03`. Binding transitions to `EXPIRED` (challenge window elapsed) or remains `PENDING` (still within window — owner may retry).

This makes the "system-only" property a protocol invariant, mirroring CIP-14-aligned §6.2's selector-reservation pattern.

### 5.7 Reverification

The CIP-5 timer (one per binding, scheduled in §5.6) fires `_reverify_external(fqdn)`, which:

1. Charges `EXTERNAL_REVERIFY_FEE` (§5.8) from the binding owner.
2. If insufficient balance: `status = SUSPENDED`, reason = `INSUFFICIENT_REVERIFY_FEE`. No verifier job dispatched.
3. Otherwise dispatch the same DNS verification job as §5.3.
4. On success: refresh `verified_at` and `next_reverify_at`; reschedule timer.
5. On failure: `status = SUSPENDED`, reason = `TXT_MISMATCH` / `CNAME_DRIFT` / `ACME_DELEGATION_MISSING` (set by the verifier callback).

Owner-initiated `reverify_external(fqdn)` is also exposed for ad-hoc revalidation (e.g., after fixing a DNS problem on a SUSPENDED binding).

### 5.8 Reverification fee (new — closes the free-ride gap)

The original CIP-16 leaves external bindings free after attachment; reverify cost falls on the protocol's verifier capacity indefinitely. CIP-16-aligned introduces a small recurring fee:

```
EXTERNAL_REVERIFY_FEE  = <governance-set>     // CBY per reverification firing
```

Charged from the binding owner's account at each reverify firing. Routed through `system:registry_settlement_config` (same splits as registration fees). Insufficient balance → `SUSPENDED` (§5.7).

A binding owner can prepay reverify cost by holding sufficient balance; the protocol does not require an explicit "deposit". Owners who let their balance run out get suspended, not slashed — recovery is `reverify_external(fqdn)` after topping up.

### 5.9 Detachment

`detach_external(fqdn)` — caller is owner. Unschedules the reverify timer, transitions to `DETACHED`, allows the FQDN to be reattached later via a fresh `begin_attach_external`.

### 5.10 Reverify timer `fee_payer` (CIP-5 revision alignment)

CIP-5 (revised 2026-04-20) §6.3 introduces a per-fire `fee_payer` model: every CIP-5 timer fire is itself metered and pre-charged. The reverify timer scheduled in §5.6 / §5.7 MUST be scheduled with `fee_payer = binding.owner`.

Two distinct fee surfaces now apply to a single reverification:

| Surface | Source | When charged | Fail-mode |
|---|---|---|---|
| Timer fire (`max_cost`) | CIP-5 §6.3 | At timer fire, before `_reverify_external` runs | `TimerCancelledInsufficientFunds`; reverify never attempted |
| `EXTERNAL_REVERIFY_FEE` | §5.8 above | Inside `_reverify_external` step 1 | `INSUFFICIENT_REVERIFY_FEE`; binding → `SUSPENDED`, no verifier dispatch |

Because the timer-fire charge happens BEFORE the handler runs, an owner who can't cover `max_cost` will see the timer silently self-destruct without ever entering `_reverify_external`. The binding stays in its prior status (typically `ACTIVE`) but no reverification occurs — and the next reverify is never scheduled either, since scheduling happens inside `_reverify_external` step 4. Without intervention this leaves the binding in a "frozen-ACTIVE" state past `next_reverify_at`.

Mitigation:

- The Route Registry MUST subscribe to `TimerCancelledInsufficientFunds` events whose `timer_id` matches a scheduled reverify timer (looked up via the reverify-timer index it maintains).
- On receipt, the Route Registry transitions the corresponding binding to `SUSPENDED` with reason `INSUFFICIENT_TIMER_FUEL` (a new reason code distinct from `INSUFFICIENT_REVERIFY_FEE`).
- §7.1's existing `current_block > next_reverify_at + EXTERNAL_REVERIFY_GRACE_BLOCKS` overdue check provides a second-line defense if the event-subscription path is missed.

This adds one new `SUSPENDED` reason to §6:

```
INSUFFICIENT_TIMER_FUEL    // owner balance < CIP-5 timer max_cost at fire time
```

Recovery is identical to other SUSPENDED reasons: owner tops up balance and calls `reverify_external(fqdn)`.

---

## 6. Status transitions

```
PENDING   → ACTIVE       // §5.6 callback succeeds
PENDING   → EXPIRED      // challenge window elapses (timer-driven)
PENDING   → DETACHED     // owner cancels before activation
ACTIVE    → SUSPENDED    // §5.7 reverify failure or §5.8 insufficient fee
SUSPENDED → ACTIVE       // owner-initiated reverify_external succeeds
ACTIVE    → DETACHED     // owner detaches
SUSPENDED → DETACHED     // owner detaches
EXPIRED   → DETACHED     // owner detaches (or auto-prune after EXPIRED_RETENTION_BLOCKS)
```

`SUSPENDED` reasons enumerated: `TXT_MISMATCH`, `CNAME_DRIFT`, `ACME_DELEGATION_MISSING`, `INSUFFICIENT_REVERIFY_FEE`.

---

## 7. Gateway behavior

### 7.1 Resolution

Gateway queries the Route Registry with the fully normalized FQDN. For external bindings, additionally:

- Status must be `ACTIVE`.
- `current_block ≤ next_reverify_at + EXTERNAL_REVERIFY_GRACE_BLOCKS`. Defense against a Gateway with stale state: even if the on-chain `status` is still `ACTIVE`, treat the binding as effectively `SUSPENDED` if reverification is overdue.
- TLS certificate present and valid (Gateway control plane responsibility, not on-chain).

### 7.2 Serving policy (corrected status codes)

| Binding status | HTTP response |
|---|---|
| `PENDING` | `503 Service Unavailable` + `Retry-After: 60` |
| `SUSPENDED` | `503 Service Unavailable` + `X-Cowboy-Error: BINDING_SUSPENDED` |
| `EXPIRED` | `404 Not Found` |
| `DETACHED` | `404 Not Found` |

The original §10.2 suggested `421 Misdirected Request` for `SUSPENDED`. HTTP/2's `421` semantics ("this server is not authoritative for the requested URI") instructs the client to retry against a different connection / Gateway, which is the wrong behavior when the binding itself is suspended — no other Gateway will succeed either. `503` correctly signals "temporary service unavailability" and avoids unnecessary retries.

### 7.3 Verified host injection (corrects host-header trust gap)

The `IngressDispatch` instruction (CIP-14-aligned §6.1) injects two extra fields into the `HttpRequestEnvelope`:

```
HttpRequestEnvelope {
  ...                    // CIP-14 fields (method, path, query, headers, body, host, request_id)
  verified_fqdn:    string,                 // injected by GatewayRegistry from DomainBinding lookup
  namespace_kind:   u8,                     // injected
}
```

Actors should branch on `verified_fqdn` (and `namespace_kind` if multi-binding) rather than the raw `host` header, which is set by the client and is attacker-controllable in the absence of system mediation. The original `host` field is retained for backward compatibility but is for informational use only.

A multi-binding actor (e.g., one serving both `api.alice.cow` and `api.example.com`) uses `verified_fqdn` to route per-tenant — this is the only field the protocol attests.

### 7.4 First-party TLD DNS

Same as original §10.3. Cowboy-controlled DNS authority for `.cow` / `.cowboy` serves records directly from the Route Registry namespace. No TXT proof or external ACME delegation needed for first-party labels.

---

## 8. Constants

```
NAMESPACE_COWBOY_NETWORK         = 0
NAMESPACE_FIRST_PARTY_TLD        = 1
NAMESPACE_EXTERNAL               = 2

TLD_COW                          = 1
TLD_COWBOY                       = 2

CHALLENGE_EXPIRY_BLOCKS          = 43_200        // ~12 hours
EXTERNAL_REVERIFY_INTERVAL       = 2_592_000     // ~30 days
EXTERNAL_REVERIFY_GRACE_BLOCKS   = 86_400        // ~1 day grace beyond next_reverify_at
EXTERNAL_REVERIFY_FEE            = <governance>  // CBY
EXPIRED_RETENTION_BLOCKS         = 7_776_000     // ~90 days; bindings auto-pruned after this
CANONICAL_EDGE_HOSTNAME          = "edge.cowboy.network"
ACME_DELEGATION_ZONE             = "acme.cowboy.network"
DNS_VERIFIER_EXECUTOR_HASH       = <built-in executor hash, governance-pinned>

DNS_VERIFY_RUNNERS               = 3
DNS_VERIFY_THRESHOLD             = 2
DNS_VERIFY_MIN_RESOLVERS         = 3
```

---

## 9. Security delta vs. original

| Threat | Original mitigation | Aligned mitigation |
|---|---|---|
| Wrong verification mode for non-deterministic DNS | `Deterministic` + TEE | `MajorityVote` with N=3 runners × `min_resolvers=3` per check (§5.3) |
| `complete_attach_external` "system-only" but no enforcement primitive | Hand-waved | `SystemInstruction::ExternalDomainCallback` with sender allowlist `RESULT_VERIFIER=0x03` (§5.6) |
| Reverify capacity free-ridden indefinitely | Not addressed | Per-firing `EXTERNAL_REVERIFY_FEE` debits owner; insufficient balance → SUSPENDED (§5.8) |
| Actors trusting attacker-controllable `host` header | Convention | `verified_fqdn` injected by GatewayRegistry; raw `host` informational only (§7.3) |
| `421 Misdirected Request` triggers wrong client retry | Suggested in original | Replaced with `503 Service Unavailable` (§7.2) |
| `RouteRegistration` schema silently replaced | Not migrated | Explicit migration with default field values for legacy records (§3.1) |
| Gateway with stale state continues serving suspended binding | Not addressed | `current_block > next_reverify_at + grace` ⇒ treat as SUSPENDED (§7.1) |

---

## 10. Known centralization risks (explicit — extends original §11.5)

The following are inherent to interoperating with the existing DNS / TLS ecosystem at v1. Mitigation is operational (multi-sig over zone updates, certificate transparency monitoring), not protocol-level:

- **ACME control plane** (`_acme-challenge → acme.cowboy.network`): the Cowboy-operated ACME zone holds delegated authority for issuance against attached domains. Compromise of this zone enables certificate misissuance for any attached domain. A future CIP may introduce a multi-party ACME design or "bring your own certificate" mode.
- **Anycast edge** (`edge.cowboy.network`): a single hostname that all attached domains CNAME to. The DNS authoritative for this name is a centralized component; anycast routes traffic but does not distribute authority over the name itself.
- **First-party TLD authority** (`.cow`, `.cowboy`): Cowboy's registry-level operation is a separately governed trust point. ICANN-rooted DNS prevents this from being trustless at v1.
- **DNS verifier executor** (`DNS_VERIFIER_EXECUTOR_HASH`): the hash is governance-pinned, meaning governance can change the verification logic by updating the hash. A compromised governance multisig could approve a verifier that always returns `match`.

---

## 11. Backwards compatibility

Additive over CIP-14-aligned. The `RouteRegistration → DomainBinding` migration (§3.1) is a one-time schema upgrade triggered at the protocol upgrade boundary; it does not change behavior for existing records — they continue to resolve through the `cowboy.network` namespace with `status = ACTIVE` defaults and no reverification cycle.

Gateways without CIP-16-aligned implementation simply cannot serve first-party TLD or external attached domains — `*.cowboy.network` continues to work.

---

## 12. Future work

| Item | Status |
|------|--------|
| Wildcard external domain attachment (`*.example.com`) | Deferred (carried from original §13) |
| DNSSEC-native verification path (skip CIP-2 verifier) | Deferred (carried) |
| Delegated registrars / reseller model for `.cow` / `.cowboy` | Deferred (carried) |
| Bring-your-own certificates | Deferred (carried) |
| Domain tokenization / marketplace | Deferred (carried) |
| Multi-party ACME (decentralize the `acme.cowboy.network` zone) | Deferred — surfaced by §10 |
| SRV-only edge mode (drop anycast requirement) | Deferred — surfaced by §5.4 |

---

## Part III — Cross-Cutting Conventions (verbatim from former `alignment-conventions.md`)

# Alignment Conventions for CIP-14 / CIP-15 / CIP-16

**Status:** Draft alignment companion (non-modifying)
**Created:** 2026-04-21
**Scope:** Cross-cutting conventions used by `cip-14-dns-addressable-actors-v2.md` (Part II), `cip-15-public-asset-hosting-v2.md` (Part II), Part II of this document. Anything that would otherwise be repeated across all three drafts lives here.

This document also enumerates upstream amendments these aligned drafts assume in CIP-2, CIP-3, CIP-5, CIP-9, and the normative entitlement registry — without modifying those source documents. Each `AMEND` item is a precondition: implementing CIP-14/15/16 requires the corresponding amendment to land first.

---

## 1. System actor address allocation

The current low-byte sequence (`node/types/src/constants.rs`, `node/runner/src/system_actors.rs:11-33`) ends at `0x0B` (`RELAY_REGISTRY`). The aligned drafts continue the same dense sequence rather than jumping into the `0x10`+ range used by the original CIP-14 (`0x0011`, `0x0012`).

| Address | Name | Source |
|--------:|------|--------|
| `0x01` | `RUNNER_REGISTRY` | existing |
| `0x02` | `JOB_DISPATCHER` | existing |
| `0x03` | `RESULT_VERIFIER` | existing |
| `0x04` | `SECRETS_MANAGER` | existing |
| `0x05` | `TEE_VERIFIER` | existing |
| `0x06` | `BASEFEE_SYSTEM_ACTOR` (alias `DUAL_BASEFEE`) | existing |
| `0x07` | `ENTITLEMENT_REGISTRY` | existing |
| `0x08` | `TREASURY` | existing |
| `0x09` | `GOVERNANCE_SYSTEM_ACTOR` | existing |
| `0x0A` | `STORAGE_MANAGER` (CIP-9) | existing |
| `0x0B` | `RELAY_REGISTRY` (CIP-9) | existing |
| `0x0C` | `ROUTE_REGISTRY` (CIP-14-aligned §4) | new |
| `0x0D` | `GATEWAY_REGISTRY` (CIP-14-aligned §7) | new |
| `0x0E` | `RECEIPT_REGISTRY` (CIP-14-aligned §8) | new |
| `0x0F` | `CONTAINER_REGISTRY` (CIP-10 v2 Part II §1) | new |

Rationale: keeping the sequence dense matches `system_actors.rs` convention and avoids the appearance of a reserved block. Original CIP-14 numbers (`0x0011` / `0x0012`) are renumbered to `0x0C` / `0x0D`.

---

## 2. Entitlement registry amendments (entitlement spec §9)

Adopting the aligned drafts requires three new entries in `node/types/src/registry.rs::REGISTRY`. The registry is lexicographically sorted (enforced by `registry_is_sorted_lexicographically`); insert at the indicated positions.

### 2.1 `ingress.http` (CIP-14)

```rust
RegistryEntry {
    id: "ingress.http",
    inheritable: false,
    attested: false,
    quota: false,
    params: &[
        ParamSchema { name: "allowlist_methods",     param_type: ParamType::StrArray, required: false },
        ParamSchema { name: "max_request_bytes",     param_type: ParamType::Uint,     required: false },
        ParamSchema { name: "max_response_bytes",    param_type: ParamType::Uint,     required: false },
        ParamSchema { name: "max_query_cycles",      param_type: ParamType::Uint,     required: false },
        ParamSchema { name: "receipt_ttl_blocks",    param_type: ParamType::Uint,     required: false },
    ],
},
```

Insertion position: between `http.fetch` and `oracle.llm`.

`quota: false` is intentional and differs from the original CIP-14 §6.1 table. The manifest has no on-chain quota accumulation mechanism: every `max_*` value is a per-request **limit**, not a cumulative quota. The flag matches reality.

### 2.2 `ingress.static` (CIP-15)

```rust
RegistryEntry {
    id: "ingress.static",
    inheritable: false,
    attested: false,
    quota: false,
    params: &[
        ParamSchema { name: "static_volume_names",       param_type: ParamType::StrArray, required: true  },
        ParamSchema { name: "max_static_response_bytes", param_type: ParamType::Uint,     required: false },
        ParamSchema { name: "max_cache_bytes_total",     param_type: ParamType::Uint,     required: false },
    ],
},
```

Insertion position: immediately after `ingress.http`.

This is a **separate** entitlement, not an extension of `ingress.http`. The original CIP-15 §7.1 nests `array<StaticVolumeBinding>` (object array) inside `ingress.http.params.static_volumes` — but `ParamValue` (`node/types/src/manifest.rs:29-34`) only supports `Uint` / `Str` / `StrArray` / `AddressArray`. There is no `Object` variant and adding one would touch manifest serialization, signature digests, and codec round-trip tests for every existing actor.

`static_volume_names: StrArray` lists volume names by ordinal; per-volume cache budgets collapse to a single `max_cache_bytes_total` (Gateway operators may apply local LRU splits — not protocol-enforced).

### 2.3 `dns.attach_external` (CIP-16)

```rust
RegistryEntry {
    id: "dns.attach_external",
    inheritable: false,
    attested: false,
    quota: false,
    params: &[
        ParamSchema { name: "max_bindings", param_type: ParamType::Uint, required: false },
    ],
},
```

Insertion position: between `bridge.subscribe_event` and `econ.hold_balance`.

Required so an actor can be the *target* of `begin_attach_external`. First-party TLD and `cowboy.network` registrations remain governed only by `ingress.http`.

### 2.4 Test update

`registry_has_exactly_14_entries` (`node/types/src/registry.rs:241`) becomes `_has_exactly_17_entries`.

---

## 3. ParamValue limits (binding for spec authors)

`ParamValue` only supports four shapes (`node/types/src/manifest.rs:29-34`). The aligned drafts conform to this without proposing a `ParamValue::Object` variant, because that change would force a coordinated schema migration of every deployed manifest.

**Allowed:**
- a scalar `Uint` (≤ `u64`)
- a single `Str` (≤ 256 bytes)
- a `StrArray` (≤ 64 entries × 256 bytes)
- an `AddressArray` (≤ 64 addresses)

**Disallowed in entitlement params (workaround patterns):**
- nested objects → flatten to multiple entitlements, or two parallel `StrArray`s pairing by index
- booleans → use `Uint` with `0`/`1`
- arrays of structs → use parallel arrays
- maps → store JSON in a `Str` (deploy-time validation cannot recurse into the JSON)

If a parameter does not fit these shapes, the aligned drafts move it out of the manifest entirely (typically into a `STORAGE_MANAGER` record or a separate system-actor table that the actor owner updates by transaction).

---

## 4. System-mediated handler invocation pattern

Several flows in CIP-14-aligned and CIP-16-aligned require an actor to trust that a specific selector was invoked **only** by a specific system actor (e.g. `GATEWAY_REGISTRY=0x0D`, `RESULT_VERIFIER=0x03`). The aligned drafts implement this in the system-instruction dispatcher (`node/execution/src/system_instruction.rs`) rather than relying on SDK-side `ctx.sender` checks.

The pattern (matches the existing `BASEFEE_SYSTEM_ACTOR=0x06` idiom for `UpdateBasefee`):

1. Define a new `SystemInstruction` opcode (e.g. `IngressDispatch`, `ExternalDomainCallback`) carrying `(target_actor, selector, payload)`.
2. The dispatch handler enforces a sender allowlist: only the named system actor address may emit the opcode.
3. The dispatcher synthesises an internal `ActorMessage` whose `ctx.sender` is set to the system actor address. Ordinary `send_message` / `call_actor` from arbitrary accounts cannot reproduce this `ctx.sender` value because the message router populates `ctx.sender` from the calling tx's signer (it cannot be forged by the caller's own code).
4. **Receiving actors MUST verify `ctx.sender` against the canonical sender for that selector** (e.g. `ctx.sender == GATEWAY_REGISTRY=0x0D` for `"http.request"`; `ctx.sender == RESULT_VERIFIER=0x03` for `"_dns.callback"`). The SDK (CIP-6) decorator-based handlers MUST include this check by default; raw handlers MUST include it manually.

> **Note (revision).** An earlier draft described a 4th step in which the PVM message router would *additionally* reserve the corresponding selectors. **That proposal was withdrawn** (see `cip-14-dns-addressable-actors-v2.md` (Part II) §6.2 Note) because it broke legitimate router-actor forwarding patterns. The handler-side `ctx.sender` check above is sufficient.

This makes ingress / verifier authenticity a protocol property: `ctx.sender` is set by the message router from on-chain signer state. SDK-default sender checks at the receiving handler are mandatory.

---

## 5. Read-only handler execution (replaces "queryActor")

CIP-14-aligned introduces a new RPC and a corresponding PVM mode. The current node RPC layer (`node/rpc/src/rpc.rs:140-210`) has no read-only handler invocation today — only REST committed-state reads (`/actor/{addr}/storage`, etc.). The original CIP-14 cites a "Milestone 2 §5.2 `queryActor` primitive" that is not present in the codebase.

### 5.1 RPC

```
POST /actor/{address}/read_handler
{
  "selector":   string,        // method name, e.g. "http.request"
  "payload":    base64,        // serialized arguments
  "max_cycles": u64?,          // overrides actor entitlement up to PROTOCOL_MAX_QUERY_CYCLES
  "min_block":  u64?           // optional consistency floor
}
→ {
  "block_height": u64,
  "result":       base64,      // handler return bytes
  "cycles_used":  u64
}
```

### 5.2 PVM mode

`PvmExecutor::execute_handler` gains a `read_only: bool` argument. When true, the host:

- Returns from `state_get` / `state_scan_prefix` as today.
- Traps on every mutating syscall — see §5.3 for the exhaustive table.
- Returns `Address::ZERO` for `caller` and `None` for `ctx.sender` (no transaction context).

Implementable with one new `HostContext` flag plus per-syscall guard clauses.

### 5.3 Permitted vs. trapped syscalls (definitive table)

Names match `node/execution/src/pvm_host.rs` exactly. This table supersedes the original CIP-14 §8.3.1, which used several syscall names that do not exist in the host (e.g. `set_storage`, `set_timeout`, `transfer`, `create_volume`, `entitlement_params`).

| Syscall | Read-only | Notes |
|---|---|---|
| `state_get` | ✅ permitted | committed state read |
| `state_scan_prefix` | ✅ permitted | committed state read |
| `state_set` | ❌ trapped | mutates own KV |
| `state_delete` | ❌ trapped | mutates own KV |
| `send_message` | ❌ trapped | mutates target mailbox |
| `call_actor` | ❌ trapped | synchronous cross-actor call |
| `schedule_timer` | ❌ trapped | mutates timer queue |
| `schedule_timer_ex` | ❌ trapped | mutates timer queue |
| `extend_timer` | ❌ trapped | mutates timer queue |
| `cancel_timer` | ❌ trapped | mutates timer queue |
| `submit_job` | ❌ trapped | dispatches off-chain task |
| `token_transfer` | ❌ trapped | mutates token balances |
| `token_transfer_from` | ❌ trapped | mutates token balances |
| `create_deferred_tx` | ❌ trapped | mutates deferred tx pool |
| `upgrade_self` | ❌ trapped | replaces actor code |
| `emit_event` | ❌ trapped | appends to event log |
| `randomness` | ❌ trapped | host RNG is consensus-derived; no consensus context on read path |

Ambient context syscalls (`block_height`, `block_timestamp`, `self_address`) are permitted; they read fields from `HostContext` rather than calling the host trait.

Trap code: `ERR_READONLY_VIOLATION` (new). Gateway maps to HTTP `500` with `X-Cowboy-Error: READ_ONLY_VIOLATION`.

The `randomness` trap fixes a bug in the original CIP-14 §11.3 determinism argument — `randomness` is exposed at `pvm_host.rs:1372` and would have allowed read-path divergence between Gateways without this trap.

---

## 6. Settlement / fee distribution reuse

CIP-3 routes burn / treasury / runner-tip splits through `SettlementConfig` stored at `GOVERNANCE_SYSTEM_ACTOR=0x09` under key `system:settlement_config`, updatable via `UpdateSettlementConfig` (opcode 40, sender must be `0x09` per `system_instruction.rs`).

The aligned drafts add **two parallel configs** under the same governance actor (no new system actor required):

- `system:registry_settlement_config` — splits for name registration / renewal fees (CIP-14-aligned §4.5, CIP-16-aligned §4)
- `system:gateway_pool_config` — splits for the Gateway serving fee pool (CIP-14-aligned §7.4)

Both updated via the existing `UpdateSettlementConfig` opcode with a new `target_pool` discriminant (one new enum variant; not a new opcode). This avoids forking burn/treasury routing across multiple ad-hoc paths.

---

## 7. CIP-9 amendments (precondition for CIP-15-aligned)

> **Errata note.** An earlier revision of this section (v1) listed AMEND 9-A through 9-E claiming that `StorageCommitment`, `commit_manifest`, the `volume_id = keccak256(...)` formula, and `Visibility::Public` were missing. They are NOT missing — they are all in CIP-9 today. The corrected, smaller delta list is below; details are in `cip-9-runner-storage-v2.md` (Part II).

CIP-9 already provides the bulk of what CIP-15-aligned needs:

- `StorageCommitment` with `volume_id`, `owner`, `visibility`, `manifest_root`, `status` (CIP-9 §11.1).
- `commit_manifest(cap_token, manifest_root)` system instruction (CIP-9 §12.2).
- `volume_id = keccak256(account_address || volume_name)` (CIP-9 §11.1).
- `Visibility::Public` model for unauthenticated reads via shard metadata (CIP-9 §7.6.3) — note: original CIP-15 used `PUBLIC_READ`; the canonical CIP-9 / CBFS name is `Visibility::Public`.
- Volume status state machine `ACTIVE → GRACE_PERIOD → DELETED → GARBAGE_COLLECTING` (CIP-9 §13).

The remaining genuine gaps are detailed in `cip-9-runner-storage-v2.md` (Part II). Summary:

- **AMEND 9-G** — `GET_MANIFEST` Relay Node RPC (`cip-9-runner-storage-v2.md` (Part II) §2). Direct manifest fetch in one round trip without per-shard reconstruction; required for low-latency Gateway operation against `Visibility::Public` volumes.
- **AMEND 9-H** — `ManifestCommitted` chain event (`cip-9-runner-storage-v2.md` (Part II) §4). Powers Gateway eager cache invalidation; polling remains as a floor.
- **Pin canonical manifest serialization** to `cbfs/manifest/src/merkle.rs` (`cip-9-runner-storage-v2.md` (Part II) §3). Reuses existing CBFS bincode + RFC-6962-style Merkle (avoids the Bitcoin-style duplicate-last-leaf shape).
- **Gateway serving authority** mapped from existing CIP-9 statuses (`cip-9-runner-storage-v2.md` (Part II) §5). Uses existing `ACTIVE` / `GRACE_PERIOD` / `DELETED` / `GARBAGE_COLLECTING` rather than introducing a new `DELINQUENT` status.

(Sequence numbers AMEND 9-A through 9-E are deliberately retired to avoid confusion with the v1 list. AMEND 9-F is unallocated. New CIP-9 amendments resume at AMEND 9-G.)

If the AMEND 9-G / 9-H items have not landed, CIP-15-aligned can still be partially deployed by falling back to indirect manifest fetch (`GET_SHARD` against `__manifest__`) and time-based polling — at the cost of higher per-request latency and slower invalidation.

---

## 8. CIP-2 amendments (precondition for CIP-16-aligned)

The current `runner/src/types.rs::VerifierCheck` enum has no DNS primitive (`runner/src/types.rs:177-201`). CIP-16-aligned uses CIP-2 multi-runner verification with `VerificationMode::MajorityVote` (already implemented per `runner/src/types.rs:215`) and two new check variants:

- **AMEND 2-A** — Add `VerifierCheck::DnsTxtRecordMatch { fqdn: String, expected_value: String, min_resolvers: u32 }`. Verifier runners resolve `fqdn` via `min_resolvers` independent recursive resolvers (operator-configured public list) and report match / mismatch.
- **AMEND 2-B** — Add `VerifierCheck::DnsCnameMatch { fqdn: String, expected_target: String, min_resolvers: u32 }`. Used to check the canonical-edge CNAME.
- **AMEND 2-C** — `JobType::Custom { executor_hash, params }` already exists (`runner/src/types.rs:146-149`). CIP-16-aligned uses it for the verification job; `executor_hash` references a built-in DNS-verification executor whose hash is governance-pinned (`DNS_VERIFIER_EXECUTOR_HASH`).

The original CIP-16 §9.6 prescribes `VerificationMode::Deterministic`, which (per `node/runner/src/types.rs:217` semantics and CLAUDE.md) requires TEE + byte-identical comparison. DNS resolution is not byte-identical across resolvers / cache states; `MajorityVote` is the structurally correct mode.

---

## 9. CIP-5 amendments

None required. The aligned drafts use existing `schedule_timer`, `schedule_timer_ex`, `extend_timer`, `cancel_timer` syscalls without changes. The hard ceiling `MAX_TIMERS_PER_ACTOR=1024` (`node/types/src/constants.rs`) is treated as a constraint that motivates §10 below.

---

## 10. Receipt model (replaces SDK-conventional `_http/results/{request_id}`)

The original CIP-14 §8.4 stores command-path results in actor KV at `_http/results/{request_id}` and registers a per-request cleanup timer. With `MAX_TIMERS_PER_ACTOR = 1024`, a popular API actor exhausts its timer budget within ~1k pending requests.

CIP-14-aligned defines a `RECEIPT_REGISTRY=0x0E` system actor that owns receipt storage and lifetime. See `cip-14-dns-addressable-actors-v2.md` (Part II) §8 for the full schema. Two key properties:

- Receipts are written by the `IngressDispatch` system instruction post-handler-return, not by actor code. Actors do not consume their own KV or timer budget for receipt management.
- A single registry-wide pruning loop expires receipts via TTL, replacing per-request timers. One timer slot total, not one per pending request.

---

## 11. Whitepaper alignment

These aligned drafts respect every WP principle exercised by CIP-14/15/16. The companion the WP v2 Part III enumerates the principles and the specific clauses that uphold them, including three places where the aligned drafts knowingly bend WP framing (Gateway as a fourth node class, receipt registry as a new state surface, ACME / TLD centralization at v1).
