# Marshal Automated Sweep — Token & Cost Accounting

**Period**: 2026-07-17 06:00 UTC → 2026-08-05 12:00 UTC (~19 days, hourly cron)
**Scope**: the `marshal-pr-sweep` scheduled headless sweep (`claude -p`); excludes this interactive session
**Source**: the per-message `usage` fields in each cron session transcript (`.jsonl`), deduped by message id
**Pricing**: Claude Opus 4.x **API list-price equivalent** (see §6 — actual billing is a subscription, not metered; this is the single biggest source of confusion)

> **Three things to hold in mind before reading the numbers** (otherwise they mislead):
> 1. **The dollar figures are "what it would cost on the metered API," not a real bill.** This machine runs on a subscription (Claude Max); nothing was charged per token. `/usage` is the real figure, and its being far smaller than this report is normal and correct.
> 2. **"$14.90 per audit" is a whole-period average.** Individual audits range from ~$5 (early, shallow PRs) to ~$30 (deep-review peaks) — see §4.
> 3. **Cost is almost entirely "context re-reads" (cache-read), not "output."** More review rounds means more re-reads means a more expensive audit — and it's super-linear (see §4).

---

## 1. Summary

| Metric | Value |
|---|---|
| Sweep runs (cron) | **442** |
| Audits (deep-review actions, **incl. multi-round on one PR**) | **345** |
| Total tokens (deduped) | **2,094,192,430** (≈ 2.09 B) |
| Total cost (API-equivalent) | **$5.1k ~ $10.3k** (a range) |
| — Standard tier (primary / lower bound) | **$5,142** |
| — 1M premium tier (upper bound, essentially never fully hit) | ≈ $10,300 |
| — Per audit (**whole-period average**, standard tier) | **≈ 6.07M tokens / $14.90** (premium-tier upper bound ≈ $29.8) |
| — Per sweep run (incl. empty queues, standard tier) | ≈ 4.74M tokens / $11.63 |

> ⚠️ **What does "1M premium tier upper bound" mean?** The model here is Opus's million-token long-context variant (`claude-opus-4-8[1m]`). Anthropic bills any single request whose context exceeds 200K tokens at roughly **2×** ("long-context premium tier": cache-read $1.5→$3/M, output $75→$150/M, etc.). So the same usage folds into two conversion prices:
> - **Standard $5,142 (primary / lower bound)** = assume **every** request is priced at the ≤200K standard rate;
> - **1M premium $10,300 (upper bound)** = assume **every** request lands in the >200K premium tier — a worst case, essentially impossible to hit fully;
> - **The real value is between them**: only the deep multi-round sessions whose accumulated context passes 200K pay the premium, so the actual figure sits closer to $5.1k.
>
> In other words this is not two independent numbers but a **range $5.1k ~ $10.3k**; "1M premium upper bound" is the **ceiling** of that range. (Again: under subscription billing neither is real spend — see §6.)

> ⚠️ **What exactly is "per audit"?** One sweep run typically reviews 2–3 PRs and shares a single `find_targets` discovery + a closing summary as fixed overhead. "Per audit" here = whole-run tokens ÷ that run's audit count, so **the shared overhead is amortized in**. It is therefore not "the net cost of one isolated PR" but "the amortized cost per audit."

---

## 2. Cost composition

| Line item | Tokens | **% of tokens** | Cost | **% of cost** | Per audit |
|---|---:|---:|---:|---:|---:|
| cache-read (context re-reads) | 2,043,571,021 | **97.6%** | $3,065 | **59.6%** | $8.88 |
| cache-write (1h cache writes) | 38,146,303 | 1.8% | $1,144 | 22.3% | $3.32 |
| output (verdicts + reasoning) | 12,411,965 | 0.6% | $931 | 18.1% | $2.70 |
| input | 63,141 | 0.0% | $1 | 0.0% | $0.00 |
| **Total** | **2,094,192,430** | 100% | **$5,142** | 100% | **$14.90** |

> ⚠️ **Why does cache-read make up 97% of tokens but only 60% of cost?** Because the unit prices differ by **10–50×**: cache-read is only $1.5/M, whereas output is 50× more ($75/M) and cache-write 20× ($30/M). So:
> - **By token volume** → cache-read dominates (97%), because every round re-reads the whole cached context;
> - **By dollars spent** → it flattens to read 60% / write 22% / output 18%, because output is small but 50× pricier per token.
> These two "percentages" are not the same thing — don't conflate them.

**The dominant driver is cache-read**: each agentic deep review runs 15–80 rounds, and every round re-reads the cached system prompt + CLAUDE.md + memory + **the accumulating conversation history** (which grows the deeper you go). Low unit price, huge volume — so it dominates.

---

## 3. Itemized daily list

| Date | Runs | Audits | Rounds/session | Tokens | Tokens/audit | Cost (API-equiv) |
|---|---:|---:|---:|---:|---:|---:|
| 07-17 | 18 | 44 | 27 | 50,062,853 | 1.6M | $155.57 |
| 07-18 | 24 | 0 | 4 | 4,180,767 | — | $14.18 |
| 07-19 | 24 | 6 | 9 | 14,453,353 | 2.9M | $58.42 |
| 07-20 | 24 | 19 | 20 | 41,178,022 | 2.7M | $141.48 |
| 07-21 | 24 | 18 | 20 | 43,125,770 | 2.4M | $135.71 |
| 07-22 | 24 | 5 | 10 | 14,426,004 | 2.9M | $52.71 |
| 07-23 | 24 | 2 | 8 | 14,170,496 | 7.1M | $49.32 |
| 07-24 | 24 | 19 | 17 | 35,231,536 | 2.1M | $120.46 |
| 07-25 | 17 | 4 | 13 | 15,751,385 | 3.9M | $55.43 |
| **07-26** | 11 | 7 | **52** | 94,733,563 | **13.5M** | $188.99 |
| **07-27** | 23 | 32 | **78** | 276,482,351 | 9.5M | $618.32 |
| 07-28 | 24 | 31 | 59 | 195,964,900 | 6.8M | $471.60 |
| 07-29 | 24 | 13 | 42 | 123,489,658 | 9.5M | $310.14 |
| 07-30 | 24 | 17 | 57 | 213,356,284 | 12.6M | $468.94 |
| 07-31 | 24 | 26 | 45 | 146,446,152 | 5.9M | $378.19 |
| 08-01 | 24 | 6 | 24 | 74,946,753 | 12.5M | $182.42 |
| 08-02 | 24 | 17 | 44 | 153,345,694 | 10.2M | $358.30 |
| 08-03 | 24 | 37 | 68 | 241,167,804 | 7.5M | $598.70 |
| 08-04 | 23 | 32 | 61 | 213,544,186 | 6.7M | $518.32 |
| 08-05 (to 12:00) | 14 | 10 | 58 | 128,134,899 | 12.8M | $264.37 |
| **Total / avg** | **442** | **345** | ~45 | **2,094,192,430** | 6.1M | **$5,141.59** |

**How to read it:**
- **Empty-queue runs still cost money** (e.g. 07-18 audited 0 PRs but still spent $14 — every run fixed-runs `find_targets` + a summary). This is also **why audits (345) < sweep runs (442)**: many runs had an empty queue.
- **Cost tracks the backlog**: 07-27 (32 audits / $618) and 08-03 (37 audits / $598) are backlog peaks.
- **Note that from 07-26/27, both "rounds/session" and "tokens/audit" jump sharply** — this is the report's core finding, see §4.

---

## 4. Why did tokens spike from 07-26/27 while audit count didn't? (core finding)

**In one line: it's "each audit got deeper (rounds up 2–4×)," not "more audits," and not "a bigger context."**

Compare three measured metrics (daily medians):

| Period | Baseline static context | Rounds/session | Tokens/audit |
|---|---:|---:|---:|
| Before the divide (07-20) | 17K | **20** | **2.7M** |
| Before the divide (07-24) | 40K | **17** | **2.1M** |
| After the divide (07-27) | 18K | **78** | **9.5M** |
| After the divide (07-30) | 29K | **57** | **12.6M** |

Three lines of evidence:

1. **Not context bloat.** "Baseline static context" = the smallest cache-read among a session's first few rounds, representing the fixed size of system prompt + CLAUDE.md + memory + tools. It stays steady at **17–41K, no growth**, and is actually *lower* on 07-27. → Rules out "MEMORY.md / CLAUDE.md grew."

2. **Not more audits.** 07-20 had 15 audits, 07-27 had 29 — but tokens/audit jumped from 2.7M to 9.5M. Audits merely doubled; tokens/audit tripled–quadrupled.

3. **The real cause = rounds per audit went from ~15–20 to ~45–78 (2–4×).** More rounds means **every round re-reads the whole accumulated conversation**, so cache-read/round also rose from ~74K to ~149K (round 60 re-reads all of rounds 1–59).

**Multiplied together = super-linear**: rounds ~2.5× × per-round context ~2× ≈ tokens/audit ~4–6×. That's the arithmetic behind the sharp rise.

**Why rounds spiked — the PR mix changed.** Before mid/late July the queue was mostly shallow PRs (docs/examples cleanup, small changes) that closed in a few rounds; **from 07-26/27 the queue filled with deep, consensus-critical PRs**, each demanding heavy scout / prove / cross-repo grep / mutation reasoning / multi-lens adversarial verification:

- **CBQS #290** (24 rounds of escalate over its life), the denomination cluster cp#67/68 · cowboy#294/295
- **PVM lockdown series** (#1227/1228/1235/1237/1224/1232 … RCE / network / file / sys leaks, each requiring reading pvm source + cross-repo confirmation)
- **tx-contract slice** (#1244/1245/1246/1249, per-tx overlay + golden diffs)
- **eth-LC bridge #1200** (r5→r8, a 2500-line diff + BLS / gindex attribution)
- **runner blind-sign stack** (#200–205, multi-round nonce recovery)

Each of these naturally runs 40–80 rounds, whereas an examples cleanup might close in 10.

> **Actionable takeaway**: the per-audit cost of deep / multi-round PRs is **super-linear** — every extra round re-reads the whole session at cache-read rate. The lever for cost control is "**shorten rounds per audit**" (triage earlier, cap pointless scout rounds), not "review fewer PRs."

---

## 5. Accounting corrections

This report fixes two overestimates and one underestimate in the first-pass figures:

1. **Streaming double-count (~2×)**: transcripts log each assistant message's `usage` twice (partial + final). Deduped by message id. → Monthly total corrected from the first-pass **$10,654 to $5,142**.

2. **Audit count inflation (~3.3×)**: the text `gate-record --change-ref` appears ~3.3× per call in a transcript (streaming + tool_result echo + summary references). After dedup, real audit actions = **345** (first pass misreported 1,137).

3. **Multi-round reviews of one PR — already counted separately, correctly**: each author push changes the head sha, so every re-review (e.g. #1200's r5→r8, runner#202's three rounds) is a **distinct change-ref sha**, recorded once each. Verified: unique heads = 344, audit actions = 345, i.e. **each head reviewed 1.00× on average** (the marker system prevents re-reviewing the same head; multi-round reviews show up as multiple heads). A multi-round PR's true cost = rounds × per-audit cost (e.g. #1200's 4 rounds ≈ $60).

**Net effect**: the total was overstated 2× (→ $5.1k); the per-audit figure was in fact **underestimated** ($9.4 → $14.9), because the audit count was inflated more than the cost, and the two errors divided out to a too-low unit price.

---

## 6. Key caveat: API-equivalent ≠ actual spend

- This machine runs on **OAuth subscription login (Claude Max)**, not a metered API key (config has no `apiKeyHelper`; `~/.claude/.credentials.json` is present).
- Every dollar figure in this report is a **reference equivalent** — "what it would fold to at API unit prices" — **not a real bill**. The subscription is a flat monthly fee; nothing was charged per token.
- That is why `/usage` shows a cost far below this report — that is the real, in-subscription figure and it is **correct**. This report exists to gauge "how much API value / ROI this automation represents."

### Pricing tiers
- **Standard tier** (primary, ≤200K context): input $15/M, output $75/M, 1h cache-write $30/M, cache-read $1.5/M.
- **1M premium tier** (upper bound, >200K context ≈ 2×): cache-read $3/M, output $150/M, etc. Most deep-review requests sit near the 200K boundary, so the monthly actual falls between **$5.1k (standard) ~ $10.3k (all premium)**. The exact premium multipliers carry some uncertainty.

---

## 7. FAQ

**Q: Why does this report say $5.1k while `/usage` shows far less?**
A: Different billing models. You're on a **subscription** (flat monthly fee); nothing is charged per token. This report is a hypothetical "folded to API unit prices." `/usage` is the real-bill figure, and it being small is correct.

**Q: Why are there fewer audits (345) than sweep runs (442)?**
A: Many runs had an **empty queue** (no PR to review / all already reviewed at their current head). Empty runs still run `find_targets` + a summary — a small cost but 0 audits.

**Q: "$14.90 per audit" doesn't match the 9.5M/audit in the daily table?**
A: $14.90 is a **whole-period average** hiding large variance: shallow early PRs ~$5, deep-review peaks ~$25–30. The daily view is more precise (see §3, §4).

**Q: cache-read is 97% of tokens but only 60% of cost — contradiction?**
A: No. cache-read has the lowest unit price ($1.5/M); output is 50× more ($75/M). Token volume and dollars spent are two different axes (see §2).

**Q: A PR reviewed several times — is the cost double-counted?**
A: Neither double-counted nor dropped. Each round is at a **different head**, an independent audit (each burning tokens), already counted separately in the 345. A multi-round PR's total = sum over its rounds.

**Q: Is "per-audit cost" the cost of one isolated PR?**
A: No. One run reviews 2–3 PRs and shares the `find_targets` / summary overhead; "per audit" = whole-run ÷ audits, with the shared overhead amortized in (see §1).

---

## 8. Bottom line

> At steady state, **one PR deep review ≈ 6.1M tokens / ~$15 API-equivalent** (cache-read is 60% of cost); over the past month, 442 cron runs and 345 audits ≈ **$5.1k API-equivalent** (range $5.1k–$10.3k). **Per-audit cost rises super-linearly with review depth (rounds)** — after the queue shifted to deep consensus PRs in late July, each audit's cost jumped 4–6×. **But under subscription billing none of this is real spend**; `/usage` is the actual figure.

_Prepared: Marshal metrics accounting · data through 2026-08-05 12:00 UTC_
