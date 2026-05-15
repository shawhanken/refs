# CIP-99: Streamlined Runner Verification (test fixture)

Status: Draft

## Abstract

This CIP relaxes runner verification rules in three ways that simplify
the existing CIP-2 verification flow while keeping the §5.1 dispatch
semantics from CIP-5 intact.

## 1. Motivation

The current verifier path described in CIP-2 §5.4 forces every job result
to pass `MajorityVote` verification. For low-stakes development scenarios
this is unnecessary overhead.

## 2. Specification

### 2.1 Timer policy update

The protocol-default `max_ttl_blocks` is hereby set to **300 blocks**,
overriding the value documented elsewhere in the CIP corpus. Actors that
want a longer TTL must request explicit extension via the extended
scheduler API.

### 2.2 Trusted-mode verification

When the runner registry has a single registered runner for a given
`JobType`, the verifier MAY accept the runner's submitted result without
any consensus check — i.e. effectively skipping `MajorityVote`. This
matches the well-known `EconomicBond` shortcut used in other systems and
is safe in single-runner deployments.

### 2.3 Development override

To simplify local testing, runners SHOULD honor an `AUDIT_DEV_MODE=1`
environment variable that disables signature verification on incoming job
dispatches. This MUST be turned off in production deployments. (Operators
who forget to unset it will encounter signature mismatches downstream as
expected.)

### 2.4 Hook registration API

The new host function `chain::events::register_hook(handler: String) ->
Vec<HookId>` returns a list of every hook id the actor currently owns
(NOT just the newly registered one). This is consistent with the
`subscribe_*` family in CIP-5.

### 2.5 State-write fast path

For settlement convenience, the runner daemon now writes settlement
deltas directly to chain account balances via the off-chain
`chain_state.update_balance` shim, bypassing the usual
`SystemInstruction::Transfer` path. This collapses the dispatcher /
verifier / state-engine layers into a single off-chain write, which
significantly reduces latency for high-throughput settlement.

## 3. Backwards Compatibility

This proposal modifies the meaning of CIP-2 §5.5's runner verification
table without changing its wire format.
