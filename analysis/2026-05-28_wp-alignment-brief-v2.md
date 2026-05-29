## Part III — WP-vs-CIP-Aligned Audit Brief (verbatim from former `wp-alignment-brief.md`)

# Whitepaper Alignment Brief — CIP-14-aligned / CIP-15-aligned / CIP-16-aligned

**Status:** Brief (non-modifying companion to `refs/whitepaper/`)
**Created:** 2026-04-21
**Scope:** Audit of how the three aligned drafts respect — or knowingly bend — the principles in the Cowboy whitepapers (`refs/whitepaper/`, `2026-03-21_cowboy-technical-whitepaper-revised.md`).

This brief does not propose any change to the WP itself.

---

## 1. Pure asynchronous actor model

> WP claim: actor handlers are message-driven; no synchronous external I/O within a handler.

- **CIP-14-aligned**: respected. The "query path" (read-handler RPC, the alignment-conventions content (now inlined as Part III of cip-14/15/16 v2 docs) §5) executes the same handler against committed state with all I/O syscalls trapped. The command path is an `ActorMessage` like any other; LLM / HTTP egress remains async via `submit_job` + callback. The new `IngressDispatch` system instruction is a one-way fire-and-forget message — no synchronous response.
- **CIP-15-aligned**: respected. Static-asset serving bypasses the actor entirely; nothing happens inside the handler. CORS preflight is Gateway-handled.
- **CIP-16-aligned**: respected. DNS verification is a CIP-2 off-chain job; the result arrives via the `_dns.callback` system message, not a synchronous return.

## 2. Determinism

> WP claim: every consensus-touching execution is deterministic across validators.

- **CIP-14-aligned**: tightened. The original CIP-14 §11.3 omitted `randomness` from the trapped list — present in the host at `pvm_host.rs:1372`. The aligned draft traps it on the read path, so two Gateways at the same `X-Cowboy-Block` MUST produce byte-identical responses.
- **CIP-15-aligned**: tightened. Dual `X-Cowboy-Block` + `X-Cowboy-Manifest-Root` headers (§5.1) let clients verify byte-identical replay across Gateways for static assets too — closes the version-skew gap the original left between manifest_root caching and dynamic block height.
- **CIP-16-aligned**: respects determinism *for chain state*. DNS resolution itself is non-deterministic; this is acknowledged and pushed to off-chain runners with majority voting (§5.3). The on-chain transition (`PENDING → ACTIVE`) is deterministic given a verifier majority — the same property CIP-2 already guarantees.

## 3. EIP-1559 dual-metered gas (CIP-3)

> WP claim: every fee flows through the dual-meter basefee + tip + treasury split governed by `SettlementConfig`.

- **CIP-14-aligned**: respected. Name-registration fees, reverify fees, and Gateway pool funding all route through `SettlementConfig`-style records under `GOVERNANCE_SYSTEM_ACTOR=0x09` (the alignment-conventions content (now inlined as Part III of cip-14/15/16 v2 docs) §6) using the existing `UpdateSettlementConfig` opcode with a new `target_pool` discriminant. No new burn / treasury machinery is invented.
- **CIP-15-aligned**: respected. No new fee surface; static serving is uncharged at the protocol level. The new "delinquency halt" rule (§5.3) ties Gateway serving authority to existing CIP-9 storage-fee accounting, rather than adding a parallel billing event.
- **CIP-16-aligned**: respected. `EXTERNAL_REVERIFY_FEE` (§5.8) is governance-priced and routed through the same registry settlement config.

## 4. Off-chain compute via Runners with verification (CIP-2)

> WP claim: anything non-deterministic, network-bound, or compute-heavy goes off-chain to runners with optional N-of-M verification.

- **CIP-14-aligned**: respected. The async LLM example handler (§8.5) uses `submit_job` exactly as today; the only change is that the callback writes to `RECEIPT_REGISTRY` instead of actor KV.
- **CIP-15-aligned**: not exercised. Static-asset serving is not off-chain compute.
- **CIP-16-aligned**: respected and extended. The new `DnsTxtRecordMatch` and `DnsCnameMatch` checks fit the existing `VerifierCheck` enum (`runner/src/types.rs:177`) — adding variants is the established extension pattern for new verification primitives. `MajorityVote` mode is already implemented (`runner/src/types.rs:215`); the aligned draft uses it. Original CIP-16's `Deterministic` choice was structurally wrong for non-deterministic DNS.

## 5. Actor immutability with explicit upgrade hatch

> WP claim: deployed actor code is immutable except via the explicit `sys.upgrade` entitlement.

- **CIP-14-aligned**: respected. §4.8 enumerates both real upgrade paths (router proxy and `upgrade_self`) and tells authors to pick one. The original §7.8 silently relied on immutability for the router pattern but did not acknowledge that `upgrade_self` already exists in `pvm_host.rs:1765` — readers could be confused into building proxies when in-place upgrade was available.
- **CIP-15-aligned**: respected. Route manifest updates are a separate authority (`update_route_manifest` from actor owner), letting routes evolve without changing actor code — this *strengthens* the immutability story by externalizing routing config from the immutable code.
- **CIP-16-aligned**: respected. No actor-code touchpoints.

## 6. Entitlement-gated capability surface

> WP claim: every privileged actor capability flows through a manifest-declared entitlement, validated against the normative registry at deploy time.

- **CIP-14-aligned**: respected. `ingress.http` is **proposed as** a new `RegistryEntry` in `node/types/src/registry.rs::REGISTRY` (precondition for CIP-14 v2 activation; the registry currently has 14 entries and would gain a 15th). The aligned draft drops the original's "Quota: ✅" because the registry has no on-chain quota accumulation primitive — `quota: false` matches reality. **Until the registry entry actually lands in code, CIP-14 v2 cannot activate.**
- **CIP-15-aligned**: respected. Separate `ingress.static` entitlement (proposed as a 16th registry entry; precondition for CIP-15 v2 activation) keeps the param schema flat (works inside actual `ParamValue` shape constraints — no nested objects needed). Coexistence rule: declaring `ingress.static` without `ingress.http` is rejected.
- **CIP-16-aligned**: respected. New `dns.attach_external` entitlement (proposed 17th registry entry) gates external attachment per actor. Same activation precondition as CIP-14/15 v2: the registry entry must land in code before CIP-16 v2 can activate.

## 7. Self-sovereign service primitive

> WP claim: an actor + protocol services should suffice to host a verifiable internet service without external hosting infrastructure.

- **CIP-14-aligned**: respected. Adds the missing protocol service (Gateway pool) so the actor can be reached without operating a server.
- **CIP-15-aligned**: respected. Adds the missing protocol service (Gateway-served public assets) so the actor can ship a website without operating a CDN.
- **CIP-16-aligned**: respected, with explicit limitations (§10 of CIP-16-aligned). External attached domains require external DNS authority — a sovereignty boundary the protocol cannot remove without alternative roots like Handshake.

---

## 8. Where the alignment knowingly bends the WP framing

These are not violations — they are extensions the WP did not anticipate, surfaced by the CIP-14/15/16 work.

- **Gateway as a fourth node class** (CIP-14-aligned §7): the WP frames "off-chain participants" mostly as runners. The aligned drafts add Gateways as a distinct ingress class with their own staking, health, and incentive pool. Justified by CIP-10's "no ingress" constraint on runner containers — runners architecturally cannot do ingress, and validators / relay nodes are wrong roles for it.
- **Receipt registry as a fourth state surface** (CIP-14-aligned §8): the WP storage model centers on actor KV, mailboxes, and timers. Receipts are a new dedicated surface owned by `RECEIPT_REGISTRY=0x0F`. Justified by the `MAX_TIMERS_PER_ACTOR=1024` constraint — per-request cleanup timers would exhaust the budget on any popular actor.
- **ACME / first-party TLD centralization at v1** (CIP-16-aligned §10): the WP's "self-sovereign service" framing implies trustless infrastructure. CIP-16-aligned acknowledges that v1 sits inside the ICANN root and the existing CA system, with operational mitigation (multi-sig, transparency logs) rather than protocol-level trustlessness.

---

## 9. Open WP-level questions surfaced by this exercise

These do not block the aligned drafts, but should land in a future WP revision:

1. **Stake vs. operating balance separation for service-providing nodes.** The runner section already implicitly separates stake (slashable collateral) from gas balance (spendable). Gateways follow the same model in CIP-14-aligned §6.3 + §7.2. The WP should generalize this: any service-providing node has both, and mixing them is a category error.

2. **Read-only handler execution (`read_handler` RPC) as protocol primitive.** The aligned drafts treat it as protocol-normative (Gateways depend on PVM trap semantics for safety, not just RPC convenience). The WP should reflect that read-only execution is part of the consensus-defined PVM contract, not just an RPC convenience layer.

3. **Receipt / response-storage primitive that generalizes beyond ingress.** The pattern in CIP-14-aligned §8 (system-actor-owned, single-pruning-loop receipt registry) likely applies to any system actor that mediates third-party calls (oracle dispatch, future cross-chain bridges, etc.). The WP could promote it from a CIP-14 detail to a general "deferred result" pattern.

4. **System-mediated handler invocation as a first-class pattern.** The selector-reservation idiom used in CIP-14-aligned §6.2 (`"http.request"` reserved at the PVM router) and CIP-16-aligned §5.6 (`ExternalDomainCallback` allowlisted to `RESULT_VERIFIER=0x03`) is not unique to ingress — it's the protocol-level analog of `internal` / `external` visibility in EVM contracts. The WP could surface it as a recurring pattern.

5. **Static config storage at `STORAGE_MANAGER` for actor-owned routing / CORS / etc.** CIP-15-aligned moved route_manifest and cors_config out of the volume and into on-chain state at `STORAGE_MANAGER`. This pattern (chain-resident, owner-mutable, atomic with deploys) likely generalizes — many "deployment-scoped configuration" surfaces would benefit from the same model rather than reinventing per-feature storage.
