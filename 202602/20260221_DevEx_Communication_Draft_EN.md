# DevEx & Cowchat — Product Design & User Journey Alignment


## Two Entry Points, One Shared Backend

Cowboy serves two different types of users, but both share the same underlying capabilities (RPC API, Actor deployment pipeline, on-chain state queries):

```
                                                ┌──────────────────┐
  Technical Developers ──── DevEx CLI ─────────→│                  │
                                                │  Cowboy Devnet   │
                                                │  (RPC / Chain /  │
  Non-technical Users ── Cowchat ── LLM Layer ─→│   Actor Engine)  │
                               (Natural Lang →  └──────────────────┘
                                 CLI Cmds / RPC)
```

Both paths share the same end goal: **enabling users to successfully deploy and run Actors on Cowboy.** The difference is the entry point — technical users interact directly through CLI commands, while non-technical users interact through natural language, which an LLM translates into equivalent CLI commands and RPC calls. **In essence, Cowchat is a natural language frontend for the CLI.**

---

## User Journey 1: DevEx (Technical Developer Path)

For developers who can write Python, completing the full workflow through CLI and SDK.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                       DevEx User Journey Map                                 │
├─────────────┬──────────┬────────────┬──────────┬────────────┬────────────────┤
│ ① Install  │ ② Setup  │ ③ Code    │ ④ Deploy│ ⑤ Observe  │ ⑥ Iterate     │
│ (first-time)│          │            │          │            │                │
├─────────────┼──────────┼────────────┼──────────┼────────────┼────────────────┤
│ User        │ Create or│ Use        │ Deploy   │ View Actor │ Based on       │
│ installs    │ connect  │ scaffolding│ Actor to │ runtime    │ observations,  │
│ CLI tool    │ wallet,  │ to init a  │ Devnet   │ status,    │ modify code,   │
│ with a      │ claim    │ project,   │ with a   │ transaction│ re-deploy,     │
│ single      │ test     │ write      │ single   │ results,   │ observe again, │
│ command     │ tokens   │ Actor on   │ command  │ and logs   │ iterate        │
│             │ from     │ templates  │          │            │                │
│             │ faucet   │            │          │            │                │
├─────────────┼──────────┼────────────┼──────────┼────────────┼────────────────┤
│ cowboy      │ cowboy   │ cowboy     │ cowboy   │ cowboy     │ Reuse tools    │
│ CLI         │ wallet   │ init       │ actor    │ actor logs │ from ③④⑤     │
│ installer   │ create/  │ + SDK      │ deploy   │ + status   │ in a loop      │
│             │ connect  │ + docs     │          │ queries    │                │
│             │ + faucet │            │          │            │                │
└─────────────┴──────────┴────────────┴──────────┴────────────┴────────────────┘
```

**Core experience**: From installation to seeing their Actor running on-chain, the process should be as fast and smooth as possible. Every step should have a clear command and immediate feedback.

---

## User Journey 2: Cowchat (Non-Technical User Path)

For users who don't write code, completing the same workflow through natural language conversation. Cowchat is powered by an LLM that translates user's natural language into the exact same CLI commands and RPC calls used in the DevEx path. **The steps are fundamentally the same — only the interaction method differs.**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       Cowchat User Journey Map                                  │
├──────────┬────────────┬────────────┬────────────┬────────────┬──────────────────┤
│ ① Enter │ ② Onboard  │ ③ Describe│ ④ Confirm │ ⑤ Monitor  │ ⑥ Adjust        │
│          │ (first-    │            │  & Deploy  │            │                  │
│          │  time)     │            │            │            │                  │
├──────────┼────────────┼────────────┼────────────┼────────────┼──────────────────┤
│ User     │ Get an     │ Describe   │ Cowchat    │ User asks  │ User tells       │
│ opens    │ account    │ the Actor  │ presents   │ in chat:   │ Cowchat "adjust  │
│ Cowchat  │ with       │ in natural │ generated  │ "how is my │ the strategy",   │
│ website, │ wallet and │ language:  │ Actor plan │ actor      │ system modifies  │
│ enters   │ test       │ "build me  │ for user   │ doing?"    │ and re-deploys.  │
│ the chat │ tokens.    │ a trading  │ to review, │ Cowchat    │ All within the   │
│ interface│ (Wallet    │ bot"       │ confirm or │ responds   │ same chat        │
│          │ mgmt TBD)  │            │ modify,    │ with status│ conversation     │
│          │            │            │ then deploy│ summary    │                  │
├──────────┼────────────┼────────────┼────────────┼────────────┼──────────────────┤
│ Cowchat  │ Wallet     │ Chat-based │ Plan       │ Chat-based │ Chat-based       │
│ website  │ create/    │ intent     │ preview    │ status     │ adjustment       │
│          │ connect    │ input      │ & confirm  │ query &    │                  │
│          │ + faucet   │            │ in chat    │ response   │                  │
│          │ (mech TBD) │            │            │            │                  │
├──────────┼────────────┼────────────┼────────────┼────────────┼──────────────────┤
│          │ LLM        │ LLM        │ LLM        │ LLM        │ LLM translates   │
│ No LLM   │ translates │ interprets │ generates  │ translates │ "adjust" into    │
│ needed   │ onboard    │ user intent│ Actor code │ "how is my │ code changes +   │
│          │ requests → │ & breaks   │ & converts │ actor      │ cowboy actor     │
│          │ wallet cmd │ into       │ into       │ doing?" →  │ deploy command   │
│          │ + faucet   │ structured │ cowboy     │ RPC query  │                  │
│          │            │ request    │ actor      │ commands   │                  │
│          │            │            │ deploy cmd │            │                  │
└──────────┴────────────┴────────────┴────────────┴────────────┴──────────────────┘
```

**Core experience**: After opening Cowchat and onboarding, the entire journey happens within the conversation. **The user never needs to leave the chat interface.**

