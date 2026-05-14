# 🥊 Relative Competitor Analysis

<!-- Notion page id: e55e6c7d-52db-83fb-b032-817f3cdccab0 -->


## TL;DR

- Cowboy's unique value proposition. 
  - Verifiable compute alone won't differentiate Cowboy - every Category A competitor markets it; buyers can't tell them apart. 
  - Python-first developer experience is the real wedge against EVM-based AI L1s, but it's *not* unique against ASI:Chain (MeTTa), NEAR (Rust/WASM), or Olas (Python at the framework level). 
  - Sovereignty / agentic-citizens framing is the only ideological positioning in Category A that resonates with crypto-natives.
- Standards (x402, MPP, ERC-8004) sit above L1s but solve different problems. 
  - x402 and MPP are competing payment standards (both reviving HTTP 402).
    - Add x402 endpoint compatibility for actors. 
    - As of April 2026, x402 has processed ~165M transactions and ~$50M cumulative volume across ~69,000 active agents. [[source](https://cryptonews.com/news/coinbase-x402-ai-agent-app-store-crypto-payments/)]
  - ERC-8004 is an identity/reputation registry. 
    - Integrate ERC-8004 reference contracts (live on mainnet Jan 29, 2026; the spec itself is still **Draft**, and the Validation Registry is not yet user-accessible) for portable actor identity and reputation.
  - Cowboy must integrate, not compete with them. 
    - Payment volume flows to whoever speaks the standard, not whoever has the cleverest tokenomics.
  - MPP launched alongside Tempo mainnet on March 18, 2026 - already live with 100+ integrated services (OpenAI, Anthropic, Mastercard, Visa, etc.). It is not a future watch-item; it is a present competitor to x402. [[source](https://cryptonews.com/news/coinbase-x402-ai-agent-app-store-crypto-payments/)]
- Runner subsidies have an Olas-style risk 
  - Subsidised activity can mask weak unit economics once incentives taper. 
  - Track the ratio of subsidy-driven to organic actor revenue - if it doesn't trend organic, there's an overhang.
- Tokenomics models worth studying
  - NEAR's fee buyback (note: NEAR also has emissions of ~2.5% annual; the buyback offsets, not replaces, them). 
  - Sahara's automated upstream revenue split is the best primitive for compositional agent economies. 
  - 0G's pre-funded broker with deferred-batch settlement is the right pattern for high-frequency micropayments without per-call gas.
- Avoid the ASI path 
  - The *Fetch.ai v. Ocean Protocol Foundation* case (filed Nov 4, 2025, S.D.N.Y., case 1:25-cv-9210) alleges Ocean converted ~661M OCEAN into ~286M FET and sold ~263M FET (~$120M at the time of conversion, not $263M).  [[source](https://cryptoslate.com/cryptos-flagship-ai-pact-fracture-fetch-sues-ocean-over-263m-fet-community-sales/)]
  - Settlement talks have been underway since late October 2025 - the case may not go to trial, but FET dropped >90% from peak during the dispute. 
  - The lesson is governance-failure risk, not the dollar figure.
- The biggest competitive risk isn't another L1 
  - It's Virtuals + x402 on Base. ~17,000–18,000 agents deployed. [[source](https://coinstats.app/ai/a/fundamental-analysis-virtual-protocol)]
  - Agentic GDP of ~$400–470M as of early 2026, expanding to BNB Chain and XLayer in Q2 2026. 
  - "Why Cowboy not Base + Virtuals + x402?" must be answerable in two sentences. 
    - The strongest answers, in order: Python-native DX, Cycles/Cells decoupling actor execution from gas-fee volatility (note: Cycles still cost something - they denominate compute differently, they aren't free), and sovereignty as ideological brand.

## The four real categories

Grouping these projects by tech stack alone is misleading - what actually matters is what they're trying to be and who they're competing against. 

Four distinct categories emerge. Note that several projects span categories, and the visual map at the end of this section reflects that.


#### Category A - AI Compute L1s

**Members:** 0G, Sahara AI, ASI:Chain, Ritual, HeLa, and Cowboy

**What they're competing for**

- The inference and verifiable-compute workload. 
- The competitor set is both other crypto AI projects (for crypto-native mindshare) and AWS, Azure, GCP, OpenAI, Anthropic (for the actual workload). 
**Defining features**

- Purpose-built consensus or precompiles for AI workloads; on-chain or chain-attested inference; native marketplaces for compute, models, or datasets; some flavour of cryptographic verification (TEE, ZK, VRF, or sampling).
**The shared thesis**

- Purpose-built AI infrastructure with verifiable compute can undercut centralised cloud on price (90% claims are common, none independently benchmarked) while offering provenance and sovereignty guarantees that AWS structurally cannot.
**Where Cowboy sits within this group**

- Closest to Ritual on the verifiability axis (VRF-based verifiable off-chain compute is structurally similar to Ritual's Infernet + ZK proofs).
- Distinguished by:
  1. Python as the primary developer surface for an *L1 with verifiable compute*. ASI:Chain uses MeTTa, NEAR uses Rust/WASM, Olas uses Python at the framework level (not the L1 level). This is a narrower but more defensible claim than "Python-first AI L1."
  1. The Cycles/Cells resource model (ICP-derived). End users don't see gas-fee volatility, but Cycles still represent a real cost - the model decouples UX from gas, it doesn't eliminate cost.
  1. The explicit "agentic citizens" sovereignty framing. Cowboy is the only project in this category positioning the agent itself - not the human owner - as the first-class economic and political actor.

#### Category B - Agent Payment Rails

**Members:** Kite AI, Tempo (Stripe/Paradigm)

**What they're competing for**

- The machine-to-machine payment settlement layer. Competitor set is Stripe, Visa, and the broader card networks - *not* compute providers.
**Defining features**

- Stablecoin-native settlement
- Identity primitives for agents (Kite's Agent Passport, Tempo's session model)
- Explicit support for x402, MPP, or both.
**The shared thesis**

- That agent-to-service transactions need their own settlement rail because (a) traditional card networks can't price per-API-call micropayments, and (b) general-purpose L1s congest under payment workloads. 
- Both projects deliberately sideline the native token from the transaction loop. 
- Tempo has no native gas token - fees settle in stablecoins. 
- Kite uses USDC/PYUSD/USDT for payments and reserves KITE for staking and access.
**The standards fight matters more than the chain fight**

- x402 and MPP are *both* implementations of the same idea (reviving HTTP 402 for agent payments), not competing visions. The differences:
  - x402 (Coinbase + Cloudflare, May 2025): permissionless, chain-agnostic, multiple facilitators, processed ~$24M cumulative by December 2025 and ~$50M cumulative / ~$600M annualised by April 2026.
  - MPP (Stripe + Tempo, March 18, 2026): rail-agnostic by design (extended for cards via Visa, Lightning via Lightspark), session primitive for streaming micropayments, deeply integrated with Stripe's PaymentIntents API. Already live with 100+ integrated services at launch.
Whichever standard wins shapes which chain captures the volume.


#### Category C - Privacy-First Agent Runtimes

**Members:** NEAR (post-pivot), HeLa, partially Cowboy

**What they're competing for**

- Workloads where confidentiality of inputs, prompts, or model weights is the binding constraint - institutional finance, healthcare, regulated industries, and adversarial agent workloads.
**Defining features**

- TEE-based execution (Intel SGX, AMD SEV-SNP), confidential GPU marketplaces, hardware-attested inference, fee abstraction so users pay in whatever token they hold.
**The shared thesis**

- Plaintext on-chain inference is unacceptable for high-value workloads. 
- Whoever owns the trusted execution layer for agents owns the institutional segment.
**Note on overlap**

- HeLa straddles A and C.
- Cowboy's verifiable-compute design has *limited* confidentiality implications. To be precise: VRF-based sampling provides verifiability of *which* computation was selected, not privacy of inputs/outputs. Cowboy is not a privacy-positioned chain in the way NEAR (IronClaw, TEEs) or HeLa (TEE + ZK) are. The earlier framing of "partial Category C" overstated this.
- NEAR is the purest privacy-first play here post-pivot (though "pivot" is also a strong word - see correction in Section 2.4).

#### Category D - Agent Tokenization Protocols (not L1s, but in the conversation)

**Members:** Virtuals Protocol, Olas

**What they're competing for**

- Capital formation around individual agents. 
- Closer to a launchpad/marketplace than infrastructure.
**Defining features**

- Every agent gets its own token; tokens pair against a base liquidity asset (VIRTUAL, OLAS); revenue from agent activity accrues to token holders; the protocol takes a cut of every launch and every interaction.
**Why they're in the conversation despite not being L1s**

- They have the most operational agent activity of anyone in this report. 
- Virtuals reports ~17,000–18,000 agents deployed, Agentic GDP of ~$400–470M as of early 2026, and protocol revenue annualising around $300M. 
- Olas-powered agents reportedly account for the majority of Safe transactions on Gnosis Chain (the often-cited "75%+" figure should be sourced and dated when used externally - it fluctuates). 
- Any L1-native project has to articulate why a dedicated chain beats Virtuals-on-Base or Olas-on-Gnosis for a specific use case.

#### Competitive Landscape


|  | Compete with cloud (A) | Compete with Stripe (B) | Compete on privacy (C) | Compete on capital formation (D) |
|---|---|---|---|---|
| EVM-native | 0G, Sahara, Ritual, HeLa | Kite, Tempo | HeLa | Virtuals, Olas |
| Non-EVM | ASI:Chain (MeTTa), **Cowboy** | - | NEAR (Rust/WASM) | - |

Caveat: HeLa appears in both A and C; Olas operates across multiple host chains (Ethereum, Gnosis, Base, Optimism, Polygon, Solana, plus others - call it "multiple" rather than a precise count). The map is a sorting aid, not a definitive taxonomy.


## Takeaways for Cowboy

These are framed against Cowboy's known positioning: a Python-native L1 with the Actor VM, Cycles/Cells resource model, VRF-based verifiable off-chain compute, dual delegation with LSTs, runner subsidies, and explicit agentic-citizens / sovereignty thesis.


#### 1. Cowboy's category is real but crowded - differentiation has to come from developer experience and the sovereignty story, not the verifiability claim alone

Verifiable compute is the most-claimed and least-delivered feature in Category A. Every project here markets some flavour of "cryptographic proofs of correct execution." Buyers (developers, enterprises, agent builders) cannot easily distinguish TEE attestations from VRF sampling from full ZK, and most don't try. A pure "verifiable compute" wedge is unlikely to differentiate Cowboy in a buyer's first 30-second comparison.

What *can* differentiate:

- Python as the developer surface for a verifiable-compute L1. Solidity is the default in EVM-based Category A projects; ASI:Chain has its own DSL (MeTTa); NEAR uses Rust. If Cowboy's CLI + SDK + Claude context files genuinely let an AI engineer go from "I have an agent" to "my agent is on-chain and earning" in under an hour, that's the wedge - but it's a wedge against EVM-based AI L1s and against Rust-based NEAR, not a unique Python position. Olas already uses Python at the framework level on top of host EVM chains, and any well-resourced competitor could ship a Python wrapper.
- The sovereignty framing is the only ideological positioning in this category that resonates with the existing crypto-native audience. 0G and Sahara are pitching to enterprises; Cowboy is the only project explicitly aligning with the "your agent shouldn't live on someone else's platform" thesis. Don't dilute this.
Cowboy's specific weaknesses worth honestly naming (this section is sparse and should be developed further):

- Pre-mainnet vs. live competitors with shipped agent activity (Virtuals, Olas, 0G).
- A new chain to learn vs. integrating with existing chains and standards.
- Validator security and ecosystem depth at launch will lag established L1s.

#### 2. The standards layer (x402, MPP, ERC-8004) is where the action is - Cowboy must integrate, not compete

These three are not coequal standards solving the same problem. x402 and MPP are competing payment standards (both based on HTTP 402). ERC-8004 is an identity/reputation registry standard - it explicitly leaves payment out of scope.

Cowboy should integrate all three as a settlement target rather than building competing primitives:

- ERC-8004 for actor identity and reputation. Reference contracts went live on Ethereum mainnet on Jan 29, 2026, but the spec itself remains a Draft EIP, and the Validation Registry component is still under technical due diligence and not user-accessible. Adoption is real but early - calling it "a de facto standard" overstates current reality. Integration is one-time work and gives Cowboy actors portable identity that can be discovered from any EVM chain that integrates 8004 (Base is the announced next deployment target).
- x402 endpoint compatibility for any actor exposing a service. An actor that speaks x402 can be paid by any x402-aware agent without further integration. The cost is a thin shim. Volume context: ~165M transactions, ~$50M cumulative, ~$600M annualised across ~69,000 active agents as of April 2026. Coinbase facilitates >50% of x402 volume but the protocol is permissionless with multiple facilitators.
- MPP support is not optional any longer. MPP launched alongside Tempo mainnet on March 18, 2026 with 100+ integrated services at launch (OpenAI, Anthropic, DoorDash, Mastercard, Nubank, Revolut, Shopify, Standard Chartered) and design-partner extensions for cards (Visa) and Lightning (Lightspark). It is positioned as the enterprise-friendly counterpart to x402's developer-first design. Treat MPP as a present requirement, not a future watch-item.
Agent payment volume is going to flow to whoever speaks the standard, not to whoever has the cleverest tokenomics.


#### 3. The runner-subsidy model has a cautionary parallel in Olas's bonding mechanism

Cowboy's runner subsidy - paying out to actors that drive real usage - has the same intent as Olas's bonding model: bootstrapping a developer-side flywheel by routing protocol incentives to active operators. Olas's experience is instructive:

- It works, in the sense that Olas-powered agents do drive meaningful on-chain activity on Gnosis (often cited as the majority of Safe transactions; [verify with current data] before using the specific 75% figure externally).
- It is criticised, in the sense that Olas's FDV has been viewed as high relative to revenue, because the activity is largely subsidised. Once subsidies taper, the question is whether actors stay because of unit economics or because of the subsidy.
The metric to watch internally is the ratio of subsidy-driven actor revenue to organic (non-subsidised) actor revenue over time. If that ratio doesn't trend toward organic, the network has the same overhang.


#### 4. Tokenomics - the Category A models worth studying are NEAR, Sahara, and 0G; the one to avoid is ASI

Tokenomics-wise, the most relevant comparables for Cowboy:

- NEAR's fee buyback mechanism (100% of Intents fees buy back NEAR) ties token value to protocol activity. Note: NEAR also has ~2.5% annual emissions, so the buyback offsets emissions, not replaces them. The often-quoted "$177M daily volume = net deflationary" threshold should be sourced before being used externally - [verify]. The mechanism is interesting either way as a model for how Cowboy's token captures value as actor activity scales.
- Sahara's automated upstream revenue split (when an actor invokes another developer's model/dataset, fees route automatically to upstream contributors) is the most interesting structural primitive in the inference-economy group. It directly enables compositional agent economies - exactly the kind of behaviour Cowboy actors are likely to exhibit. The specific implementation details should be confirmed against Sahara's litepaper before reproducing claims.
- 0G's pre-funded sub-account broker model is a clean implementation of pay-per-inference. The deferred-batch settlement design (off-chain tracking, periodic on-chain settlement) is the right pattern for any L1 doing high-frequency micropayments without per-call gas overhead. Worth noting the doc earlier called this "the cleanest in production today" - qualify any such claim, since none of these systems have been independently benchmarked.
What to avoid: ASI Alliance. The Fetch.ai v. Ocean Protocol Foundation lawsuit (case 1:25-cv-9210, S.D.N.Y., filed Nov 4, 2025) is a worked example of how token-merger governance failures undermine credibility. The disputed amounts: ~661M OCEAN converted into ~286M FET, of which ~263M FET were sold (approximately $120M at time of conversion, not $263M as the prior version of this doc stated - the 263 was a token count, not a dollar amount). Settlement talks have been ongoing since late October 2025; Sheikh publicly offered to drop legal claims if tokens were returned. Whether the case proceeds or settles, FET fell ~90% from peak during the dispute, and Ocean Protocol formally withdrew from the alliance on October 8–9, 2025. Cowboy's dual-delegation + LST design is structurally different but has its own governance attack surface; the LST risk assessment WIP is well-aimed.


#### 5. The biggest risk to Cowboy is not another L1 - it's Virtuals + x402 on Base

The most under-appreciated competitive pressure on every Category A project is this: a developer can already deploy a tokenised agent on Base with x402 settlement and Virtuals' tokenomics, today, with no new chain. Virtuals reports ~17,000–18,000 agents deployed (the count varies by source and date), Agentic GDP of ~$400–470M as of early 2026, and protocol revenue annualising around $300M. Virtuals has also co-developed ERC-8183 with the Ethereum Foundation's dAI team - a permissionless framework specifically for agent-to-agent commerce - which further reduces the "you need a new chain" argument.

Cowboy's answer to "why a new chain?" needs to be sharper than "verifiable compute" (which can be added to Base via Ritual or similar coprocessors). The strongest answers, in order of credibility:

1. Python-native development experience that EVM-based AI L1s structurally cannot match, and that ASI:Chain (MeTTa) and NEAR (Rust) have not pursued. Most defensible, but watch for a Python wrapper from competitors - the wedge is real but copyable.
1. Cycles/Cells resource model decouples actor execution from gas-fee volatility. Real UX problem on EVM chains today. Important framing: Cycles still cost - they don't make execution free. The benefit is predictable cost, not no cost.
1. The sovereignty/agentic-citizens positioning as ideological brand. Defensible only if the network's governance and economic design genuinely deliver it (the LST risk work matters here).
The single biggest analytical hole this doc has not yet filled: what does running a Cowboy actor cost in dollar terms compared to a Base + x402 deployment? Until that comparison exists, the "two-sentence answer" to "why Cowboy not Base + Virtuals + x402?" is rhetorical, not evidenced. This should be worked out before any external pitch.
