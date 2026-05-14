# 🏔️ Initial Questions

<!-- Notion page id: ca6e6c7d-52db-83be-ab11-81310707de76 -->

1. When actors need an offchain task complete and a random committee of runners is selected to complete the action and then submit hash of result - does this create any bottleneck issues on the LLM side as you need to have 5-Yx more requests for a single Cowboy actor request?
  1. [Chad] they’re theoretically executed in parallel but we’re working on an updated protocol between runners and validators we expect to land early next week. We’re actually not sure what @% of traffic will want 
1. Whats an example of a storage heavy and compute heavy transactions?
1. How are you able to attribute cycles costs to different operations proactively? Surely some may be more complex than others so sticking to fixed costs is ineffective?
1. Treasury fee is worth a point of discussion. Worth considering removal - not many legitimate chains have a mechanism like that.
  1. **[Chad] - Fair point and it makes the math weird, i think we’re ok with that**
1. How are runner models verified? Also how are wrong results verified? Is it majority rules?
1.  Is "net deflationary at steady state" a hard goal or a preference?
  1. **[Chad] - Open to feedback, I’m not sure we have a strong preference here but net slightly inflationary is probably good. See next question…**
1. Whitepaper §8.2 says inflation is 8%/6% → 4%/3% → 2%; your design-decisions doc (in public docs) says 5% → 1.5%. Which one reflects current thinking?
  1. **[Chad] Our latest thinking is in this doc here - I’m going to update the whitepaper today to match. **[**https://docs.google.com/spreadsheets/d/1dvh2EKHpicohIjQ07OBvY6Hx5QoSvo-9vXJIibP2ARM/edit?gid=602797327#gid=602797327**](https://docs.google.com/spreadsheets/d/1dvh2EKHpicohIjQ07OBvY6Hx5QoSvo-9vXJIibP2ARM/edit?gid=602797327#gid=602797327)
  1. **The thought was that because we have real compute costs, which burn CBY, there is naturally a bit of deflationary pressure, so we want some natural inflation. The 8% seemed too high from talking to Yin and others and so we are thinking 4% year one, 3% year two, 2% steady state. See the last tab of that spreadsheet.**
1. Runner economics
  1. What does a bad runner actually look like?
    1. Taxonomy of misbehaviour - returning wrong results, skipping jobs, colluding, selective TEE bypass, timing attacks on VRF selection. You can't price slashing without a classified threat model.
  1. What's the slashing-to-attack-value ratio that holds?
    1. Stake must exceed expected attack payoff. We'd model: for each misbehaviour type, what's the attacker's gain, and what minimum stake makes it economically irrational -expressed as a function of CBY price.
  1. How do runner economics stay stable across a 10× CBY price range?
    1. They're right to worry about this. Static USD-denominated stake caps, dynamic stake adjustments, or CBY-denominated with governance-triggered resets - each has tradeoffs we can simulate.
  1. Creator codes - does an actor-originality premium make sense?
    1. They raised Hyperliquid builder codes unprompted. If actors can be copied and run identically, there's no creator moat. A fee share to the original author (enforced by the VM or by optitional registration) is a legitimate design question we can model.
