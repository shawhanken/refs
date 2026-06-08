# Design note: the `ingress.http` entitlement primitive (CIP-14)

**Date:** 2026-06-08
**Author:** Marshal (advisory)
**Status:** proposal — needs governance + maintainer decision before implementation

## Why this exists

Three independently-tracked gaps are the **same missing primitive**, not three problems:

| Gap | Where | What it needs |
|-----|-------|---------------|
| CIP-16 F2 | `register_tld_label` / `set_tld_actor` | verify the route `target` is allowed to receive HTTP ingress |
| CIP-16 F3 | `register_tld_label` | verify the caller controls `target` |
| CIP-15 §6.8 | `UpdateRouteManifest` (escape `cow1293-sec-6-8-volume-entitlement`) | verify a `static_route.volume_name` is one of the actor's bound volumes |

All three block on: **there is no on-chain representation that "actor X is authorized for HTTP ingress (and which volumes it may serve)."** Today `register_tld_label` is permissionless and `UpdateRouteManifest` carries a `TODO` because the binding does not exist to check against.

The entitlement *checker* is already generic and sufficient:
`EntitlementChecker::check_permission(grantee, scope, action, block, ts)` walks `get_grantee_entitlements` + roles. The only thing missing is the **registry entry** (`types/src/registry.rs::REGISTRY`) and a grant path for `ingress.http`. Add the entry once and all three checks become a few lines each.

## The primitive

Add `ingress.http` to the normative entitlement registry (CIP-14 §6.2), modeled on the existing `http.fetch` / `storage.blob` entries:

```rust
// types/src/registry.rs — REGISTRY (kept lexicographically sorted by id)
RegistryEntry {
    id: "ingress.http",
    // params describe what the actor is allowed to serve:
    params: &[
        // optional: cap on hostnames / routes; array<StaticVolumeBinding> for §6.8
        ParamSchema { name: "static_volumes", ty: ParamType::… },   // unblocks CIP-15 §6.8
        ParamSchema { name: "max_routes",     ty: ParamType::U64 }, // optional
    ],
}
```

Open encoding question (the second half of the CIP-15 blocker): `ParamValue` cannot currently encode `array<StaticVolumeBinding>`. Either (a) extend `ParamValue` with an array-of-struct variant, or (b) store volume bindings as a separate ROUTE_REGISTRY sub-record keyed by actor and reference them by name. (b) is smaller and avoids touching the manifest codec; recommended.

## How each gap consumes it

**CIP-16 F2 — `target` may receive ingress (register + set_actor):**
```rust
let allowed = EntitlementChecker::new(store)
    .check_permission(&target, &Scope::Actor(target), &Action::Custom(b"ingress.http".to_vec()), block_height, 0)
    .await?;
if !allowed { return Err(ExecutionError::Unauthorized); }
```

**CIP-15 §6.8 — volume authorization (`UpdateRouteManifest`):** replace the `TODO` with
`validate_route_volumes(&manifest, &allowed)` where `allowed` is read from the `static_volumes`
param of the actor's `ingress.http` grant (pure helper already implemented + tested). Kills escape
`cow1293-sec-6-8-volume-entitlement`.

**CIP-16 F3 — caller controls `target`:** two coherent models; **pick one (governance call):**
- **(A) self-administration** — require `tx.from == target` (mirrors `UpdateRouteManifest` /
  `SetActorQuota`). Zero new state, consistent with the codebase. Cost: a name must be registered
  *by the actor itself*; an EOA cannot register on an actor's behalf.
- **(B) actor-owner registry** — introduce an explicit owner/controller record for actors and
  check `caller == owner(target)`. More flexible (EOA-managed actors, delegation) but it is a new
  cross-cutting primitive with its own governance + migration surface.
  Recommendation: ship (A) now (it is free and matches every existing self-admin handler); pursue
  (B) only if product needs EOA-managed names.

## Scope / sequencing

1. **CIP-14 change (governance):** add `ingress.http` to `REGISTRY`; decide the volume-binding
   encoding (recommend the separate sub-record, option (b)).
2. **Grant path:** how an actor acquires `ingress.http` (manifest entitlement at deploy, or an
   explicit grant). Reuse the existing `EntitlementGrant` machinery.
3. **Consume in CIP-15** (`UpdateRouteManifest` §6.8) and **CIP-16** (`register_tld_label` /
   `set_tld_actor` F2; F3 via model (A)).
4. **Ratchets to close on landing:** `cow1293-sec-6-8-volume-entitlement`,
   and new CIP-16 escapes for F2/F3 if opened.

This is deliberately **not** a CIP-16 PR: it is shared CIP-14 infrastructure + a governance decision
on the volume encoding and the F3 ownership model. Doing it once removes the blocker for all three
consumers; bolting ad-hoc checks onto CIP-16 alone would leave CIP-15 §6.8 still broken and invent a
one-off ownership notion.
