---
title: "CIP-18: Payments"
description: HTTP-native payments for DNS-addressable actors. MPP (IETF HTTP Auth) as the primary wire format, x402 supported for compatibility, both collapsing to a single PaymentGate settlement layer with four payment models, an inbound EVM bridge facilitator, and conditional MCP gating.
icon: credit-card
---

<Note>
  **Status:** Draft
  **Type:** Standards Track
  **Category:** Core
  **Created:** 2026-03-08
  **Updated:** 2026-04-28
  **Requires:** CIP-3 (Dual-Metered Gas), CIP-14 (DNS-Addressable Actors), CIP-20 (Fungible Token Standard)
  **Companions:** CIP-19 (Gateway MCP Ingress) — required to activate §13 MCP gating
</Note>

## 1. Abstract

This proposal defines **payments** for DNS-addressable actors (CIP-14). Cowboy actors can charge for HTTP-accessible endpoints — and, conditionally, for MCP tool calls — through four payment models: per-request (client-paid), actor-funded budgets, prepaid passes, and epoch subscriptions.

The CIP separates **presentation** from **settlement**:

- **Presentation** is the wire format clients speak. Two are supported in parallel: **MPP** (the IETF HTTP Authentication scheme `Payment`, primary) and **x402** (Coinbase's payment header convention, supported for compatibility).
- **Settlement** is the on-chain accounting performed by the **PaymentGate** system actor at address `0x0013`. Both wire formats normalize into the same internal `PaymentIntent` and settle against the same PaymentGate state.

Supported settlement assets are native CBY, CIP-20 fungible tokens (including bridged stablecoins via the inbound bridge facilitator specified in §12), and — once the corresponding bridges exist — assets on Tempo and other networks. Fiat (card) payments are out of scope for this CIP but reachable through MPP's existing `method="card"` registration in a future revision.

A new system actor at `0x0013` manages payment policies, budgets, passes, and subscriptions. Gateways enforce payment requirements at the edge, normalize the chosen wire format, and settle on-chain through the PaymentGate.

---

## 2. Motivation

CIP-14 introduced DNS-addressable actors with Gateway-mediated HTTP ingress. In that model, query-path requests are free (Gateways absorb compute) and command-path gas is paid by the Gateway from its staked balance. This works to bootstrap, but creates four problems at scale:

1. **Free-rider problem.** Any internet client can hit any actor at zero cost. Gateways bear the burden with no per-request compensation.
2. **No actor monetization.** Actors cannot charge for their services, blocking paid APIs, data feeds, micro-SaaS, and other revenue models.
3. **Agent economy bottleneck.** Autonomous agent-to-agent commerce requires per-request settlement. Without it, agents cannot transact for each other's services.
4. **Standards convergence.** Two HTTP-native payment standards are emerging in parallel:
   - **MPP** ("Machine Payments Protocol"), authored by Tempo + Stripe, on the IETF standards track (`draft-ryan-httpauth-payment`). Uses the standard HTTP Authentication framework. Supports a registry of payment methods (evm, tempo, solana, stellar, lightning, card, stripe). Has companion specs for OpenAPI discovery and JSON-RPC/MCP transport.
   - **x402**, authored by Coinbase, in production use across the Base/Coinbase agent ecosystem. Uses custom headers (`PAYMENT-REQUIRED`, `PAYMENT-SIGNATURE`).

Cowboy adopts both. MPP is treated as primary because of its IETF trajectory, Stripe's involvement, and its non-HTTP transport extensions; x402 is supported for compatibility with the existing crypto agent ecosystem. Authors write one PaymentPolicy and clients of either ecosystem Just Work.

---

## 3. Design Goals

- **One policy, two wires.** Actors declare a single PaymentPolicy. Clients can pay using MPP or x402; both succeed against the same on-chain state.
- **MPP as primary.** The CIP is MPP-first in vocabulary (`method`, `intent`) and structure. x402 is a parallel presentation, not a peer.
- **Multiple funding models.** Per-call, actor-funded, prepaid passes, and epoch subscriptions, composable through a fallback chain.
- **Multi-asset.** Native CBY, CIP-20 tokens, and (via the bridge facilitator in §12) bridged stablecoins on EVM chains.
- **Gateway-enforced, on-chain settled.** Payment checks at the edge for low latency. Settlement on-chain for finality and replay protection.
- **Composable with existing CIPs.** Reuses CIP-3 gas metering for command-path recovery, CIP-7 epoch model for subscriptions, CIP-14 dispatch for HTTP request handling, CIP-20 for fungible token transfers.
- **Discoverable.** Gateways expose a per-actor OpenAPI document with MPP's `x-payment-info` annotations so any MPP-aware agent can discover Cowboy actors.

## 4. Non-goals

- **Fiat payment rails.** ACH/SEPA/card-issuer flows are deferred. The MPP `method="card"` and `method="stripe"` registrations exist; a future CIP can wire them in.
- **Cross-chain bridge protocol design.** This CIP specifies the **interface** that a bridge facilitator must satisfy (§12) but defers the bridge protocol itself to the existing Cowboy bridge work and follow-on CIPs.
- **Tempo bridge.** No Cowboy⇄Tempo bridge exists yet. `method="tempo"` is reserved for future activation.
- **Actor-to-actor payment gating.** Internal `send_message` between actors is not gated by this CIP. Payments apply only to external ingress.
- **Streaming metered billing.** Pay-as-you-consume billing within a single long-running request (e.g., LLM token-by-token billing) is deferred.
- **Activation of MCP gating.** §13 specifies the wire format; the actor-as-MCP-server exposure path is delegated to CIP-19.

---

## 5. Definitions

- **PaymentGate.** System actor at `0x0013` that manages payment policies, budgets, passes, subscriptions, and settles payments.
- **PaymentPolicy.** Per-actor configuration: pricing per endpoint, accepted assets, model selection (per-request / actor-funded / pass / epoch), and treasury address.
- **PaymentIntent.** The Gateway's internal, wire-agnostic representation of a payment-bearing request: `{ method, intent, payer, recipient, asset, amount, binding }`. Both MPP credentials and x402 payloads normalize to this shape before reaching PaymentGate.
- **MPP.** The Machine Payments Protocol, IETF draft `draft-ryan-httpauth-payment`. The HTTP Authentication scheme named `Payment`.
- **x402.** Coinbase's payment header convention: `PAYMENT-REQUIRED`, `PAYMENT-SIGNATURE`, `PAYMENT-RESPONSE`.
- **Method.** An MPP payment rail identifier: `cowboy`, `evm`, `tempo`, etc.
- **Intent.** An MPP payment-type identifier: `charge`, and (Cowboy-scoped) `pass`, `subscription`.
- **Bridge facilitator.** A trusted oracle that observes settlement on a non-Cowboy chain and submits a corresponding credit transaction on Cowboy. See §12.
- **Serving Budget.** CBY pool deposited by an actor owner so clients pay nothing.
- **Prepaid Pass.** A `(client, actor)`-bound block of request credits, purchased upfront.
- **Epoch Subscription.** Time-bounded unlimited access, extending CIP-7's epoch model.

---

## 6. Architecture

### 6.1 Two-layer model

```
┌─────────────────────────────────────────────────────────────────┐
│                         PRESENTATION                            │
│  ┌──────────────────────┐      ┌──────────────────────────┐     │
│  │  MPP (primary)       │      │  x402 (compatibility)    │     │
│  │  WWW-Authenticate    │      │  PAYMENT-REQUIRED        │     │
│  │  Authorization       │      │  PAYMENT-SIGNATURE       │     │
│  │  Payment-Receipt     │      │  PAYMENT-RESPONSE        │     │
│  └──────────┬───────────┘      └────────────┬─────────────┘     │
│             └─────────────┬─────────────────┘                   │
│                           ▼                                     │
│                  ┌────────────────┐                             │
│                  │ PaymentIntent  │   normalized, wire-agnostic │
│                  └────────┬───────┘                             │
└───────────────────────────┼─────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────┐
│                       SETTLEMENT                                │
│                  ┌────────▼───────┐                             │
│                  │  PaymentGate   │  policies, budgets,         │
│                  │  actor 0x0013  │  passes, subscriptions,     │
│                  │                │  nonces, fee distribution   │
│                  └────────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

A PaymentPolicy applies regardless of which wire format the client speaks. The Gateway advertises both formats in every 402 response and accepts a credential in either format on the retry. Internally, both collapse to a `PaymentIntent` before hitting PaymentGate.

### 6.2 Components

- **Gateway** (CIP-14 §5): unchanged role, extended responsibility. Now also enforces payment, advertises challenges in both wire formats, normalizes credentials, and (per §13/CIP-19) terminates MCP.
- **PaymentGate** (this CIP §8): new system actor at `0x0013`. Stateful: holds policies, budgets, passes, subscriptions, nonces.
- **Bridge facilitator** (this CIP §12): new runner role with a new entitlement. Watches EVM, submits inbound credit txs to PaymentGate. Specification only — implementation is follow-on work.
- **Compute runners** (CIP-10): unchanged. Continue to run actor handlers.

---

## 7. Payment Models

### 7.1 Per-request (client-paid)

The baseline. Clients pay per request.

**MPP flow:**

1. Client requests a gated endpoint without an `Authorization: Payment` header.
2. Gateway looks up the actor's PaymentPolicy from local state cache.
3. Gateway returns `402 Payment Required` with a `WWW-Authenticate: Payment` challenge (and a parallel `PAYMENT-REQUIRED` x402 header for compatibility).
4. Client constructs a payment credential per the chosen `method`/`intent` (e.g., `method="cowboy"`, `intent="charge"`).
5. Client retries with `Authorization: Payment <base64url-credential>`.
6. Gateway verifies the credential, dispatches the request, settles via PaymentGate.
7. Gateway returns the response with a `Payment-Receipt` header.

**x402 flow:** identical except the challenge is in `PAYMENT-REQUIRED` and the credential is in `PAYMENT-SIGNATURE`.

Revenue distribution per §18.

### 7.2 Actor-funded budget

The actor pays so the client doesn't. Useful for free tiers, onboarding, freemium.

1. Actor owner calls `PaymentGate.deposit_budget(actor, amount)`.
2. Policy sets `default_mode: "actor_funded"` for the relevant endpoints.
3. Clients request endpoints normally — no payment headers.
4. Gateway checks budget balance and rate limits before serving.
5. Gateway calls `PaymentGate.deduct_budget(actor, amount, request_id)`.
6. On budget depletion, Gateway falls back per `BudgetConfig.fallback`: either `402` (degrade to client-paid) or `503` (degrade to unavailable).

Budget is rate-limited (`rate_limit_rps`), capped daily (`daily_cap`), and optionally auto-refilled from the actor's main balance.

### 7.3 Prepaid pass

A client pre-purchases a block of request credits.

1. Client calls `PaymentGate.purchase_pass(actor, credits, beneficiary)`, paying `credits × per_request_price`.
2. PaymentGate returns a random `pass_id : bytes32`.
3. Client supplies the pass on subsequent requests:
   - **MPP:** `method="cowboy"`, `intent="pass"`, payload includes `pass_id`.
   - **x402:** `X-Cowboy-Pass: {pass_id}` header (or `scheme="cowboy:pass"` in payload).
4. Gateway verifies, decrements credits, serves.
5. Passes expire after `PASS_EXPIRY_BLOCKS`.

### 7.4 Epoch subscription

Time-bounded unlimited access, extending CIP-7's epoch-key model.

1. Client calls `PaymentGate.purchase_epoch(actor, epochs, beneficiary, payer)`.
2. PaymentGate records `(beneficiary, actor, active_until_epoch)`. Idempotent: re-purchasing during an active window extends `active_until_epoch` (rolling window, same as CIP-7). Buying epochs already covered is a no-op.
3. Sponsor model: `payer` and `beneficiary` may differ.
4. Subsequent requests need no payment headers; the Gateway checks the entitlement directly.
   - **MPP:** when no `Authorization: Payment` is present and an entitlement exists, the Gateway proceeds without challenge. A challenge with `intent="subscription"` is used only when the client wants to verify or extend.
   - **x402:** equivalent behavior; no headers needed when entitled.

### 7.5 Hybrid / fallback chain

Actors MAY combine all four models in a single PaymentPolicy. The Gateway evaluates them in order:

```
1. Endpoint is free (no matching price rule, default_mode="free")
2. Client has an active subscription covering this endpoint
3. Client supplied a valid pass with credits remaining
4. Actor's budget has balance and rate-limit headroom
5. Client supplied a valid per-request credential (MPP or x402)
6. → 402 Payment Required (challenge advertises remaining payable models)
```

The first satisfied row wins.

---

## 8. PaymentGate System Actor

**Address:** `0x0013`

PaymentGate manages all payment state. It is deployed at genesis and is upgradeable only through protocol upgrades.

### 8.1 PaymentPolicy

```
PaymentPolicy {
    actor:              Address,
    enabled:            bool,
    default_mode:       "client_paid" | "actor_funded" | "free",

    price_table:        [PriceRule],

    budget_config:      BudgetConfig | null,
    epoch_config:       EpochConfig  | null,
    pass_config:        PassConfig   | null,

    accepted_assets:    [AssetConfig],   // see §8.2
    treasury:           Address,
}
```

**PriceRule** — maps a request pattern to a model and price:

```
PriceRule {
    path_pattern:   string,       // glob or exact
    methods:        [string],     // ["GET"], ["*"], etc.
    model:          "client_paid" | "actor_funded" | "pass" | "epoch",
    amount:         u256,         // atomic units of default asset
    asset:          Address | null,
}
```

Rules are evaluated in order. If none matches, `default_mode` applies. At most `MAX_PRICE_TABLE_ENTRIES` rules.

`BudgetConfig`, `EpochConfig`, `PassConfig` are unchanged from §6 above; struct definitions in §19.

### 8.2 AssetConfig

Replaces the x402-only `scheme` field of the prior draft with an MPP-first shape:

```
AssetConfig {
    asset:          Address,             // 0x0 = native CBY
    network:        string,              // CAIP-2: "cowboy:1", "eip155:8453"
    method:         string,              // MPP method: "cowboy", "evm", "tempo"
    intents:        [string],            // MPP intents: ["charge", "pass", "subscription"]
    x402_scheme:    string | null,       // x402 compat, e.g. "cowboy:exact" or null
    decimals:       u8,
    symbol:         string,
}
```

A single AssetConfig declares both MPP and x402 surfaces simultaneously. `x402_scheme: null` means the asset is MPP-only (e.g., `method="card"` once that lands).

At most `MAX_ACCEPTED_ASSETS` entries per policy.

### 8.3 API

| Method | Args | Returns | Description |
| --- | --- | --- | --- |
| `set_policy` | `PaymentPolicy` | `void` | Set/update policy. Caller MUST be actor owner. |
| `get_policy` | `actor` | `PaymentPolicy \| null` | Public. |
| `deposit_budget` | `actor, amount` | `BudgetBalance` | Deposit CBY into actor's serving budget. |
| `withdraw_budget` | `actor, amount` | `BudgetBalance` | Owner-only withdrawal. |
| `budget_balance` | `actor` | `BudgetBalance` | Public. |
| `purchase_pass` | `actor, credits, beneficiary` | `Pass` | Funds transferred from caller. |
| `pass_balance` | `pass_id` | `Pass` | Public. |
| `purchase_epoch` | `actor, epochs, beneficiary, payer` | `EpochEntitlement` | Rolling window, idempotent. |
| `epoch_status` | `actor, account` | `EpochEntitlement` | Public. |
| `verify_payment` | `intent: PaymentIntent` | `VerifyResponse` | Validate without settling. |
| `settle_payment` | `intent: PaymentIntent` | `SettleResponse` | Atomic settle: transfer funds, consume nonce. |
| `deduct_budget` | `actor, amount, request_id` | `void` | Gateway-only. |
| `credit_inbound` | `evidence: BridgeEvidence` | `void` | Bridge-facilitator-only. See §12. |

---

## 9. Wire Format — MPP (Primary)

The Gateway's primary HTTP payment surface is MPP, per `draft-ryan-httpauth-payment`. This section defines how Cowboy uses MPP; it does not redefine MPP itself.

### 9.1 Challenge

When a request to a gated endpoint arrives without a valid credential, the Gateway returns:

```
HTTP/1.1 402 Payment Required
Cache-Control: no-store
WWW-Authenticate: Payment id="<binding-id>",
    realm="<actor>.cowboy.network",
    method="cowboy",
    intent="charge",
    expires="2026-04-28T12:05:00Z",
    request="<base64url(JCS-JSON)>",
    digest="sha-256=:<base64>:"            ; only for requests with body
PAYMENT-REQUIRED: <base64(x402 PaymentRequired JSON)>
X-Cowboy-Block: <block_height>
```

The `WWW-Authenticate: Payment` and `PAYMENT-REQUIRED` headers describe the **same** payment requirement in two formats; clients use whichever they understand.

The `request` parameter is method-specific. For `method="cowboy"`, see §9.6.1.

### 9.2 Credential

The client retries with:

```
GET /api/data HTTP/1.1
Host: <actor>.cowboy.network
Authorization: Payment <base64url(JSON)>
```

The base64url-decoded JSON contains, per MPP §5.2:

```
{
  "challenge": { "id": "...", "realm": "...", "method": "...", "intent": "...",
                 "request": "...", "expires": "...", "digest": "..." },
  "source":  "did:cowboy:0x1234...abcd",       // RECOMMENDED, see §16
  "payload": { ... }                            // method-specific, see §9.6
}
```

### 9.3 Receipt

On success, the Gateway returns:

```
HTTP/1.1 200 OK
Payment-Receipt: <base64url(JSON)>
PAYMENT-RESPONSE: <base64(x402 SettleResponse JSON)>
X-Cowboy-Block: <block_height>
```

Decoded `Payment-Receipt`:

```
{
  "status":    "success",
  "method":    "cowboy",
  "timestamp": "2026-04-28T12:01:23Z",
  "reference": "0x<cowboy-tx-hash>",
  "extra":     { "settled_amount": "1000000", "asset": "0x..." }
}
```

The `PAYMENT-RESPONSE` header carries the same information in x402's format for x402 clients.

### 9.4 Challenge binding (HMAC-SHA256)

Gateways MUST bind the `id` parameter to the challenge using HMAC-SHA256 per MPP §5.1.3. The HMAC input is the canonical seven-slot pipe-joined string:

```
input = realm | method | intent | request | expires | digest | opaque
id    = base64url(HMAC-SHA256(gateway_secret, input))
```

`gateway_secret` is per-Gateway, rotated on a schedule defined by Gateway operations. Cross-Gateway settlement is unaffected because the binding is verified by the **issuing** Gateway only; PaymentGate verifies the credential against current chain state, not against the binding.

### 9.5 Payment Methods

#### 9.5.1 `method="cowboy"`

Native CBY or CIP-20 transfer on Cowboy L1.

**Challenge `request`** (decoded):

```
{
  "amount":     "1000000",
  "asset":      "0x0000000000000000000000000000000000000000",   // CBY
  "recipient":  "0x<actor-treasury>",
  "actor":      "0x<actor-address>",
  "valid_after":  <block_height>,
  "valid_before": <block_height>
}
```

**Credential `payload`** for `intent="charge"`:

```
{
  "type":           "authorization",
  "signature":      "<base64url(ed25519-sig)>",
  "authorization": {
      "from":         "0x<payer>",
      "to":           "0x<actor-treasury>",
      "amount":       "1000000",
      "asset":        "0x0000000000000000000000000000000000000000",
      "valid_after":  <block_height>,
      "valid_before": <block_height>,
      "nonce":        "<bytes32>",
      "actor":        "0x<actor-address>",
      "request_hash": "<bytes32>"
  }
}
```

The signature is over the Cowboy canonical authorization encoding using the payer's account Ed25519 key. `request_hash` binds the credential to the specific request envelope (cross-actor and cross-endpoint replay protection). `nonce` is consumed atomically on settlement.

#### 9.5.2 `method="evm"`

ERC-20 stablecoin payment on an EVM chain (Base, Ethereum, etc.). Settlement requires the inbound bridge facilitator (§12). Two credential subtypes are supported, both following MPP's EVM charge spec (`draft-evm-charge`):

- **`type="permit2"`** (RECOMMENDED): client signs an EIP-712 Permit2 authorization. Bridge facilitator submits on EVM, observes settlement, and credits Cowboy.
- **`type="authorization"`**: client signs an EIP-3009 `transferWithAuthorization` (USDC, EURC, etc.). Same facilitator path.

Both result in a `PaymentGate.credit_inbound(...)` call from a facilitator-runner once the EVM-side transfer is finalized.

#### 9.5.3 `method="tempo"` (reserved)

Reserved for stablecoin charges on Tempo once a Cowboy⇄Tempo bridge exists. Schema follows `draft-tempo-charge`. Not implementable in v1.

### 9.6 Intents

#### 9.6.1 `intent="charge"`

A one-time payment. Defined for all methods. Schema per the corresponding method spec.

#### 9.6.2 `intent="pass"` (Cowboy-scoped)

Redeem credits from a prepaid pass. Defined only for `method="cowboy"` in v1.

**Challenge `request`:**

```
{
  "actor":     "0x<actor-address>",
  "endpoint":  "/api/data",
  "credits":   1                   // credits required for this request
}
```

**Credential `payload`:**

```
{
  "pass_id":   "<bytes32>",
  "signature": "<base64url(ed25519-sig over (pass_id, request_hash))>"
}
```

The Gateway verifies the pass exists, has remaining credits, and that the signature matches the pass's bound account (or any account if the pass is bearer).

#### 9.6.3 `intent="subscription"` (Cowboy-scoped)

Verify or extend an epoch subscription. Defined only for `method="cowboy"` in v1.

**Challenge `request`:** as `charge` plus `epochs: u32`.

**Credential `payload`:** for verification, an account-key signature; for extension, a charge-style authorization.

When the client already has an active entitlement, the Gateway proceeds without a challenge; the explicit `intent="subscription"` flow is used for first-time verification or for extending an existing subscription.

> **Upstream note.** `intent="pass"` and `intent="subscription"` are net-new intents. v1 scopes them to `method="cowboy"`. Once production experience justifies it, the same intents should be proposed to the IETF working group as cross-method registrations so other methods (`evm`, `solana`, `lightning`) can adopt the same vocabulary.

---

## 10. Wire Format — x402 (Compatibility)

x402 is supported as a parallel presentation. Every 402 response that carries an MPP challenge also carries an x402 `PAYMENT-REQUIRED` header describing the same requirement.

### 10.1 402 response

```
HTTP/1.1 402 Payment Required
PAYMENT-REQUIRED: <base64(JSON)>
WWW-Authenticate: Payment ...                ; MPP, in parallel
X-Cowboy-Block: <block_height>
```

The `PAYMENT-REQUIRED` JSON follows the x402 v2 schema:

```json
{
  "accepts": [
    {
      "scheme": "cowboy:exact",
      "network": "cowboy:1",
      "maxAmountRequired": "1000000",
      "resource": "https://myactor.cowboy.network/api/data",
      "description": "Query the data API",
      "maxTimeoutSeconds": 30,
      "asset": "0x0000000000000000000000000000000000000000",
      "extra": {
        "actor": "0x1234...abcd",
        "treasury": "0x5678...ef01",
        "protocol_fee_bps": 500,
        "mpp_method": "cowboy",
        "mpp_intent": "charge"
      }
    }
  ],
  "version": "2"
}
```

The `extra.mpp_method` and `extra.mpp_intent` fields are Cowboy additions that allow x402 clients to interoperate with MPP-aware infrastructure.

### 10.2 x402 schemes

- **`cowboy:exact`** — native CBY or CIP-20. Payload mirrors the MPP `method="cowboy"`/`intent="charge"` authorization (§9.5.1) with the same fields and the same Cowboy Ed25519 signature. The bytes are essentially identical; only the framing differs.
- **`exact`** (EVM) — standard x402 EIP-3009 / Permit2 scheme. Same facilitator path as MPP `method="evm"`.
- **`cowboy:pass`** — pass redemption. Payload mirrors §9.6.2.
- **`cowboy:epoch`** — subscription verification. Payload mirrors §9.6.3.

### 10.3 Payment retry

```
GET /api/data HTTP/1.1
Host: myactor.cowboy.network
PAYMENT-SIGNATURE: <base64(JSON)>
```

A request MAY include both `Authorization: Payment` (MPP) and `PAYMENT-SIGNATURE` (x402); the Gateway accepts whichever validates. It MUST NOT charge twice; on success, both wire formats receive their corresponding receipt header.

---

## 11. Wire-Format Normalization

Before reaching PaymentGate, Gateways normalize either wire format into a single internal struct:

```
PaymentIntent {
    method:        string,           // MPP method, normalized
    intent:        string,           // MPP intent, normalized
    payer:         Address,
    recipient:     Address,
    asset:         Address,
    amount:        u256,
    binding:       PaymentBinding,   // signature + nonce + request_hash
    source_wire:   "mpp" | "x402"    // for telemetry / receipts
}
```

Normalization rules:

- An x402 `scheme="cowboy:exact"` payload normalizes to `method="cowboy"`, `intent="charge"`.
- An x402 `scheme="exact"` (EVM) payload normalizes to `method="evm"`, `intent="charge"`.
- An x402 `scheme="cowboy:pass"` payload normalizes to `method="cowboy"`, `intent="pass"`.
- An x402 `scheme="cowboy:epoch"` payload normalizes to `method="cowboy"`, `intent="subscription"`.

PaymentGate sees only `PaymentIntent`. It does not know or care which wire format the client used.

---

## 12. Inbound EVM Bridge Facilitator

This section specifies the facilitator interface for `method="evm"` payments. **Implementation is deferred** — the facilitator runs as a new runner role with the `bridge.facilitate.evm` entitlement. Until that role is deployed, `method="evm"` is advertised in policies but unfulfillable.

### 12.1 Role

The bridge facilitator is a runner that:

1. **Watches** an EVM chain for a defined set of settlement events (EIP-3009 `transferWithAuthorization`, Permit2 `Transfer` from `Permit2.permitTransferFrom`).
2. **Verifies** that each observed transfer corresponds to a Cowboy payment authorization (matching nonce, recipient, amount).
3. **Submits** a `PaymentGate.credit_inbound(evidence)` Cowboy transaction that credits the corresponding CIP-20 balance to the payer's Cowboy account and consumes the payment nonce.

### 12.2 Relationship to the existing withdrawal bridge

Tony's team has built the **outbound** direction: Cowboy → Ethereum withdrawal via runner-attested block roots and Merkle-proof claims (`CowboyLightClient.sol`, `CBYBridge.sol`; see `node/examples/bridge/`). The inbound facilitator is symmetric: where the outbound runners attest Cowboy state to Ethereum, the inbound facilitator attests Ethereum state to Cowboy. Same trust pattern, same runner architecture, opposite direction.

The facilitator MAY share a runner host with the withdrawal-attestation role, but the entitlements are independent.

### 12.3 BridgeEvidence

```
BridgeEvidence {
    chain_id:        u256,                 // CAIP-2 chain identifier numeric form
    tx_hash:         bytes32,              // EVM tx hash containing the transfer
    block_number:    u64,
    block_hash:      bytes32,
    log_index:       u32,                  // index of the Transfer log
    payer:           Address,              // EVM payer
    cowboy_payer:    Address,              // mapped Cowboy account
    recipient:       Address,              // actor treasury (Cowboy)
    asset_evm:       Address,              // EVM token contract
    asset_cowboy:    Address,              // mirror CIP-20 asset on Cowboy
    amount:          u256,
    nonce:           bytes32,              // Cowboy payment nonce being settled
    confirmations:   u32,                  // observed at submission time
    facilitator_sig: bytes,                // facilitator's signature over the above
}
```

### 12.4 PaymentGate.credit_inbound

```
credit_inbound(evidence: BridgeEvidence) -> void
```

Behavior:

1. Verify `facilitator_sig` against a registered facilitator key (held by runners with `bridge.facilitate.evm`).
2. Verify `evidence.confirmations >= MIN_BRIDGE_CONFIRMATIONS_EVM`.
3. Verify `evidence.nonce` is unconsumed in PaymentGate's nonce table for `(payer, asset_cowboy)`.
4. Mint or transfer `amount` of `asset_cowboy` to the actor's treasury.
5. Consume the nonce.
6. Emit `InboundCredited(payer, recipient, asset_cowboy, amount, evidence.tx_hash)`.

If verification fails, the call reverts and the facilitator can retry with corrected evidence (e.g., more confirmations).

### 12.5 `bridge.facilitate.evm` entitlement

```
EntitlementGrant {
    id: "bridge.facilitate.evm",
    params: {
        "chains":             [u256],   // chain IDs the runner will watch
        "min_confirmations":  u32,
        "facilitator_pubkey": bytes
    }
}
```

Granted to runners that are part of the bridge oracle set. Threshold and rotation policy for facilitator keys is governed by the same governance process as the withdrawal-attestation runner set (CIP-12).

### 12.6 Failure modes

- **Reorg.** If a watched EVM transfer is reorged out before `min_confirmations`, the facilitator MUST NOT submit `credit_inbound`. If submitted prematurely and the evidence becomes invalid post-reorg, the facilitator runner forfeits the reverted gas — this is the design incentive to wait for finality.
- **Facilitator equivocation.** Multiple facilitators MAY observe the same transfer. The first valid `credit_inbound` succeeds; subsequent ones revert because the nonce is consumed.
- **Stuck payments.** Authorizations with `valid_before < current_evm_block` MUST be rejected at the facilitator layer. The Gateway's challenge MUST set `valid_before` to leave sufficient finality headroom (`EVM_FINALITY_HEADROOM_BLOCKS`).

---

## 13. MCP Gating

This section specifies how MPP's JSON-RPC / MCP transport extension (`draft-payment-transport-mcp`) applies to Cowboy actors. **Activation requires CIP-19 (Gateway MCP Ingress)**, which defines the `/_cowboy/mcp` endpoint, MCP version (2025-11-25), and the dispatch contract from MCP `tools/call` to actor invocation. CIP-18 specifies only the wire payment portion.

### 13.1 Endpoint

When CIP-19 is active, every actor with the `ingress.http` and `payment.gate` entitlements automatically exposes:

```
https://<actor>.cowboy.network/_cowboy/mcp
```

This is an MCP server using streamable HTTP transport (MCP 2025-11-25). The Gateway terminates the connection.

### 13.2 `tools/list` generation

The Gateway generates the MCP tool list from the actor's HTTP route table (per CIP-14) and the OpenAPI document of §14. Each declared HTTP endpoint becomes an MCP tool. Authors do not write a separate MCP manifest.

### 13.3 `tools/call` dispatch

A `tools/call` request maps to the same actor dispatch (query path or command path per CIP-14 §8) that the equivalent HTTP request would have used. The actor handler is unchanged; it does not know whether it was invoked via HTTP or MCP.

### 13.4 Payment challenges over JSON-RPC

When a `tools/call` requires payment and no valid credential is supplied, the Gateway returns a JSON-RPC error:

```json
{
  "jsonrpc": "2.0",
  "id": <request-id>,
  "error": {
    "code": -32402,
    "message": "Payment Required",
    "data": {
      "challenges": [
        {
          "id": "...",
          "realm": "<actor>.cowboy.network",
          "method": "cowboy",
          "intent": "charge",
          "expires": "...",
          "request": "<base64url(JCS-JSON)>"
        }
      ]
    }
  }
}
```

Error code `-32402` mirrors HTTP's 402 status. The `data.challenges` array uses the same MPP challenge schema as §9.1.

### 13.5 Credentials and receipts via `_meta`

Clients submit credentials in the JSON-RPC request `_meta` field per `draft-payment-transport-mcp`:

```json
{
  "jsonrpc": "2.0",
  "id": <request-id>,
  "method": "tools/call",
  "params": {
    "name": "fetch_data",
    "arguments": { ... },
    "_meta": {
      "payment-authorization": "<base64url(MPP-credential)>"
    }
  }
}
```

Receipts are returned in the response `_meta`:

```json
{
  "jsonrpc": "2.0",
  "id": <request-id>,
  "result": {
    "content": [...],
    "_meta": {
      "payment-receipt": "<base64url(MPP-receipt)>"
    }
  }
}
```

### 13.6 Out of scope here

- The streamable HTTP endpoint, MCP capability negotiation, and `tools/list` generation rules are specified in CIP-19.
- x402 has no MCP transport equivalent; MCP gating is MPP-only.

---

## 14. Discovery via OpenAPI

Gateways auto-generate a discovery document per actor at:

```
GET https://<actor>.cowboy.network/_cowboy/payment/openapi.json
```

The document is an OpenAPI 3.1 spec annotated with MPP's `x-payment-info` (per `draft-payment-discovery-00`):

```yaml
openapi: 3.1.0
info:
  title: <actor> API
  x-service-info:
    categories: [...]
    docs: https://...
paths:
  /api/data:
    get:
      summary: Query the data API
      x-payment-info:
        method: cowboy
        intent: charge
        amount: "1000000"
        asset: "0x0000000000000000000000000000000000000000"
        currency: CBY
      responses:
        '200': { ... }
        '402': { ... }
```

The Gateway derives this document from:
- Routes registered for the actor (CIP-14 Route Registry).
- The actor's PaymentPolicy `price_table` and `accepted_assets`.
- Any optional `openapi_metadata` declared in the policy (titles, descriptions, schemas).

This makes Cowboy actors discoverable by any MPP-aware agent that has never heard of Cowboy.

---

## 15. Gateway Integration

This section extends CIP-14's Gateway behavior with payment enforcement. CIP-19 will further extend it for MCP termination.

### 15.1 Request flow (HTTP)

1. Gateway receives an HTTP request for a registered actor (CIP-14 §7).
2. **Payment check (NEW):** Gateway reads PaymentPolicy from local cache.
3. If endpoint is free → dispatch (CIP-14 §8).
4. If client has an active subscription covering this endpoint → dispatch.
5. If a pass credential (MPP `intent="pass"` or x402 `cowboy:pass`) is present → verify, decrement, dispatch.
6. If actor-funded budget has balance and rate-limit headroom → deduct, dispatch.
7. If a per-request credential is present (MPP `Authorization: Payment` or x402 `PAYMENT-SIGNATURE`) → normalize to PaymentIntent, verify with PaymentGate, dispatch, settle.
8. Otherwise → return 402 with parallel MPP and x402 challenges.

### 15.2 Query path payment

For GET/HEAD requests with payment:

1. Gateway verifies the credential locally (against its committed view of PaymentGate state).
2. Gateway runs the actor handler via `queryActor` (no consensus).
3. Gateway submits `PaymentGate.settle_payment(intent)` as a fire-and-forget transaction.
4. If settlement fails (e.g., nonce already consumed by a concurrent Gateway), the Gateway absorbs the cost. This incentivizes correct local verification.

### 15.3 Command path payment

For state-mutating requests:

1. Gateway verifies the credential.
2. Gateway constructs a `GatewayRegistry.dispatch()` transaction (CIP-14 §9.2) with payment context attached.
3. PaymentGate settles atomically with request execution in the same transaction.
4. Gas recovery (`gateway_recovery`) is paid out per CIP-14's existing model.

### 15.4 Policy caching

Gateways MUST cache PaymentPolicy in their local state view. Refreshed every block; policy changes take effect in the block following commitment. Reuses the same cache infrastructure as Route Registry and entitlement data.

---

## 16. Client Identity

### 16.1 DID format

Cowboy account addresses appear in MPP's `source` field as:

```
did:cowboy:<lowercase-hex-address>
```

For example: `did:cowboy:0x1234abcd...`. This DID method is registered (informally) by this CIP. Future revisions may publish a formal DID method spec.

### 16.2 Payment-derived identity

For `intent="charge"` flows, the payer address from the credential's `authorization.from` field IS the client identity. No separate identity headers are required.

### 16.3 Account signature for non-paying flows

For pass and subscription redemption where the credential does not itself transfer funds (the funds were transferred at purchase time), the client signs a small canonical struct over `(challenge.id, request_hash)` with their account key. The signature appears in `payload.signature`.

### 16.4 Session tokens

**Future work.** Browser-friendly session tokens are not specified here. MPP has no answer either; this is an open problem across both standards.

---

## 17. Reserved Paths

Added to the `/_cowboy/` namespace (extending CIP-14 §8.6):

| Path | Method | Description |
| --- | --- | --- |
| `/_cowboy/payment/policy` | GET | Public policy doc (JSON). |
| `/_cowboy/payment/openapi.json` | GET | OpenAPI 3.1 with `x-payment-info`. See §14. |
| `/_cowboy/payment/quote` | POST | Price quote for a hypothetical request. |
| `/_cowboy/payment/pass/{pass_id}` | GET | Pass details. |
| `/_cowboy/payment/subscription` | GET | Subscription status for the authenticated client. |
| `/_cowboy/payment/budget` | GET | Public budget balance. |
| `/_cowboy/mcp` | * | MCP endpoint, when CIP-19 is active. |

---

## 18. Revenue Distribution

```
Per-request payment:
    total_amount = actor_fee + protocol_fee + gateway_recovery
    actor_fee     ─────────> Actor treasury
    protocol_fee  ─────────> Protocol treasury (burned or governed)
    gateway_recovery ──────> Gateway (command-path gas only; 0 for query path)

    protocol_fee = floor(actor_fee × PROTOCOL_PAYMENT_FEE_BPS / 10_000)
```

Pass and subscription purchases:

```
total = credits × per_request_price       (pass)
total = epochs × fee_per_epoch            (subscription)
protocol_fee = floor(total × PROTOCOL_PAYMENT_FEE_BPS / 10_000)
actor_receives = total - protocol_fee
```

For actor-funded budgets, the same fees apply but the actor pays from its budget rather than the client paying directly.

---

## 19. Protocol Constants

```
PAYMENT_GATE_ADDRESS              = 0x0013
PROTOCOL_PAYMENT_FEE_BPS          = 500           // 5%
MAX_PRICE_TABLE_ENTRIES           = 100
MAX_ACCEPTED_ASSETS               = 10
MIN_BUDGET_DEPOSIT                = <governance-set>
MAX_EPOCH_BLOCKS                  = 2_592_000     // ~30 days
DEFAULT_EPOCH_BLOCKS              = 86_400        // ~1 day
PASS_EXPIRY_BLOCKS                = 31_536_000    // ~1 year
MAX_PREPAID_CREDITS               = 1_000_000
CBY_ASSET_ADDRESS                 = 0x0000000000000000000000000000000000000000
PAYMENT_POLICY_CACHE_TTL_BLOCKS   = 1
MIN_BRIDGE_CONFIRMATIONS_EVM      = 32            // governance, per chain
EVM_FINALITY_HEADROOM_BLOCKS      = 64
JSONRPC_PAYMENT_REQUIRED_CODE     = -32402
```

`BudgetConfig`, `EpochConfig`, `PassConfig` struct definitions:

```
BudgetConfig { rate_limit_rps: u32, daily_cap: u256,
               fallback: "402"|"503", auto_refill: bool }
EpochConfig  { fee_per_epoch: u256, epoch_blocks: u32,
               min_purchase: u32, max_purchase: u32 }
PassConfig   { min_credits: u32, max_credits: u32, expiry_blocks: u64 }
```

---

## 20. Entitlement: `payment.gate`

```
EntitlementGrant {
    id: "payment.gate",
    params: {
        "accepted_methods":      ["cowboy", "evm"],
        "accepted_intents":      ["charge", "pass", "subscription"],
        "max_price_per_request": u256
    }
}
```

| Param | Type | Description | Default |
| --- | --- | --- | --- |
| `accepted_methods` | `array<string>` | MPP methods the actor may declare in its policy | `["cowboy"]` |
| `accepted_intents` | `array<string>` | MPP intents the actor may declare | `["charge"]` |
| `max_price_per_request` | `u256` | Consumer-protection upper bound | governance |

**Prerequisite:** the actor MUST also hold `ingress.http` (CIP-14). Payment gating without HTTP ingress has no effect.

---

## 21. Security Considerations

- **Replay (single chain).** Authorizations carry a `nonce` consumed atomically on settlement. Replay across endpoints is prevented by `request_hash` binding the credential to the request envelope. `valid_before` / `valid_after` block-height bounds limit lifetime.
- **Replay (cross-wire).** A credential submitted as both MPP and x402 in the same request is allowed; the Gateway settles once. Submitting the same payment payload across two requests is prevented by nonce + `request_hash`.
- **Replay (inbound bridge).** The facilitator's `credit_inbound` consumes the same nonce table as direct Cowboy authorizations, so an EVM-side payment cannot be claimed twice.
- **Cross-Gateway double-spend.** PaymentGate consumes the nonce atomically. Two Gateways that both verify the same credential locally will not both successfully settle; the loser absorbs the gas.
- **Stale challenges.** The MPP `expires` parameter and the Cowboy `valid_before` block height bound credential lifetime independently. Both MUST be respected.
- **HMAC binding.** The challenge `id` is HMAC-bound to the challenge parameters per §9.4. A client cannot tamper with the request body, recipient, or amount and reuse the `id`.
- **Price manipulation.** Policy changes commit on-chain and take effect in the following block. Within a single block's challenge-then-retry, the price cannot change.
- **Pass enumeration.** `pass_id` is a random `bytes32`. Sequential enumeration is infeasible.
- **Budget DoS.** Actor-funded budgets are protected by `rate_limit_rps`, `daily_cap`, and the auto-refill threshold.
- **Bridge facilitator compromise.** A compromised facilitator could submit fraudulent `credit_inbound` calls. Mitigated by:
  - Multi-runner facilitator quorum (governance-set threshold).
  - PaymentGate verifying `facilitator_sig` against the registered facilitator key set.
  - `MIN_BRIDGE_CONFIRMATIONS_EVM` providing reorg headroom.
  - The same recovery mechanisms as the withdrawal-attestation runner set (CIP-12 governance).
- **Protocol fee evasion.** All payment paths route through PaymentGate. Gateways only accept settlements processed by PaymentGate.

---

## 22. Rationale

**Why both MPP and x402?** They are presentation layers over the same substrate. Supporting both makes Cowboy actors payable by the entire active agent ecosystem (Coinbase / Base) and the emerging IETF / Stripe ecosystem simultaneously. The marginal Gateway implementation cost is low because the underlying signing primitives are nearly identical.

**Why MPP as primary?** It is on the IETF standards track, backed by Stripe, and has companion specs we want (OpenAPI discovery, JSON-RPC/MCP transport). x402 is informal and EVM-specialized. MPP becomes the long-term winner for HTTP-native payments; x402 is for short-term ecosystem reach.

**Why decouple wire from settlement?** The previous draft of this CIP conflated x402 wire framing with PaymentGate mechanics, making it hard to add a second wire format. The two-layer model lets us add MPP without rewriting accounting and lets future wire formats (e.g., a hypothetical "exact" Solana scheme) plug in by adding a normalizer.

**Why route MCP through the Gateway, not the runner?** The Gateway is the public, DNS-addressable edge. It already enforces payment, terminates HTTP, and dispatches. Adding JSON-RPC termination preserves the architecture: runners stay private compute, payment enforcement stays in one place, actors don't opt into "I'm an MCP server" — their handlers are MCP tools by virtue of being HTTP-callable. Putting MCP on runners would require exposing them publicly, duplicating payment enforcement, and forcing a new actor-side declaration.

**Why is the inbound bridge facilitator a separate runner role?** Watching another chain is an oracle responsibility, not an ingress or compute responsibility. It maps cleanly onto the existing withdrawal-attestation runner pattern (Tony's team) — symmetric, in the opposite direction, with the same trust model. Sharing host with withdrawal runners is allowed; conflating roles in a single entitlement is not.

**Why scope `intent="pass"` and `intent="subscription"` to `method="cowboy"` initially?** Upstream registration with the IETF is valuable but slow. Cowboy-scoped intents let us ship now; once we have production data, proposing them upstream as cross-method intents is a credible RFC.

**Why extend CIP-7's epoch model for subscriptions?** CIP-7 already solved rolling-window epoch billing with idempotent purchases and sponsored payers. Reusing it keeps the billing model consistent across streams and HTTP/MCP endpoints.

**Why `0x0013`?** Sequential allocation. CIP-7 reserves `0x0006`, CIP-14 reserves `0x0011` and `0x0012`. `0x0013` is next.

---

## 23. Future Work

- **Fiat rails.** `method="card"` and `method="stripe"` (already MPP-registered) wired into PaymentGate via a Stripe facilitator role.
- **Tempo bridge.** `method="tempo"` becomes implementable once a Cowboy⇄Tempo bridge exists.
- **Session tokens.** Browser-friendly subscriptions without per-request signing.
- **Streaming metered billing.** A `intent="meter"` for pay-as-you-consume billing within long-running requests (e.g., LLM token-by-token).
- **Upstream `intent="pass"` and `intent="subscription"`.** Propose to the IETF working group as cross-method intents once production usage justifies the RFC.
- **Actor-to-actor payment gating.** Extend payment enforcement to internal `send_message` calls.
- **MPP discovery beyond OpenAPI.** Bazaar / actor index integration with `x-service-info` metadata for cross-actor agent discovery.

---

## 24. Backwards Compatibility

This CIP is fully additive to CIP-14:

- Actors without `payment.gate` are unaffected. Their endpoints remain free / Gateway-subsidized.
- Gateways continue to serve free traffic for non-gated actors using the existing CIP-14 flow.
- The PaymentGate system actor is deployed at `0x0013`, previously unallocated.
- `/_cowboy/payment/*` and `/_cowboy/mcp` reserved paths do not conflict with CIP-14's reserved paths.
- The `payment.gate` and (future) `bridge.facilitate.evm` entitlement IDs are new.
- No changes to the CIP-3 fee model, CIP-7 stream protocol, or CIP-20 token standard are required.

The previous draft of CIP-18 (titled "Payment Gating", x402-only, dated 2026-03-08) is **not** preserved for migration. It was unshipped and no production code depends on it.
