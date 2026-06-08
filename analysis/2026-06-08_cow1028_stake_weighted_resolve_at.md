# COW-1028 — stake-weighted `resolve_at` (implementation draft)

**Date:** 2026-06-08 · **Author:** Marshal (advisory) · **Status:** draft — needs the staking-subsystem decision below before coding

Pins the requirement Marshal flagged on #630: governance is currently **fail-closed**
(`resolve_at` Defeats any proposal while `voting_snapshot_total == 0`), and the stake
chamber is an unweighted address count. COW-1028 turns governance on by making it
stake-weighted per CIP-12 §6.2. The `#[ignore]`d test `runner/src/types.rs::resolve_at_enforces_stake_quorum`
(ratchet `governance.stake_weighted_quorum`) must go green when this lands.

## 0. Blocking dependency — there is no validator-staking subsystem yet

Grounded against `origin/devnet` (2026-06-08):
- **No validator stake / delegation on-chain.** Runner staking exists (`RunnerRegistration.stake`,
  CIP-2/CIP-13) but that is *runner* stake, not the *validator* self+delegated stake §6.2 needs.
- **No active-stake accessor.** There is no `total_active_stake(block)` / per-staker weight lookup.
- **Validator set lives in consensus (commonware), not an execution-queryable registry.**
- **Vote records store only the choice byte** (`vec![if support {1} else {0}]`) — no weight.

So COW-1028 **must first define/land** (or depend on a prior CIP for):
1. Validator self-stake + delegation accounting (with the §6.2 7-day unbonding-queue rule).
2. A snapshot mechanism: total active stake + per-staker frozen weight at a block.
3. Execution access to the active validator set + count at a block.

The rest of this draft is concrete for the parts that are determinable today and flags the
above as inputs.

## 1. Data-model changes (`runner/src/types.rs::Proposal`)

- `for_votes` / `against_votes`: `u64` (address counts) → **`u128` stake sums**. Add
  `abstain_votes: u128` (§6.2 abstain counts to quorum, not approval).
- Keep `voting_snapshot_total` / `validator_snapshot_total`; populate them at promotion (below).
  Add `voting_snapshot_block` / `temp_check_snapshot_block` if not already present.
- **Vote record** (`vote_key`) must store the voter's *frozen stake weight* alongside the choice,
  so a vote-change can subtract the exact weight it added (codec: `choice_byte || weight_le`).

## 2. Snapshot at temp-check → voting promotion

At the promotion site (`SubmitProposal` Tier-0 immediate path + `EndorseProposal` threshold path,
`system_instruction.rs`), set:
```rust
proposal.voting_snapshot_block   = block_height;
proposal.voting_snapshot_total   = staking.total_active_stake(block_height);   // DEP (§0.2)
proposal.validator_snapshot_total = validators.active_count(block_height);     // DEP (§0.3)
```
`temp_check_snapshot_total` is taken at submission (§6.4) for the temp-check denominator.

## 3. `CastVote` — weight by frozen stake (replaces `+1`)

```rust
// weight is the voter's stake frozen at voting_snapshot_block (0 if unstaked → §6.2 zero weight)
let w = staking.weight_at(tx.from, proposal.voting_snapshot_block);   // DEP (§0.2)
if w == 0 { return Err(ExecutionError::Unauthorized); }               // unstaked CBY can't vote
// on change, subtract the previously-stored weight from the old side first
match support { true => proposal.for_votes += w, false => proposal.against_votes += w }
// store choice + w in the vote record for exact reversal
```
Delegation (§6.2): absent an override the delegated weight votes with the validator; a delegator
MAY override per proposal (cheap System-lane message). The override path is a DEP of the staking
subsystem.

## 4. `resolve_at` — stake quorum + approval (concrete; uses existing `TierParams`)

```rust
pub fn resolve_at(&self, current_block: u64) -> Option<ProposalState> {
    if current_block <= self.voting_deadline_block { return None; }
    // fail-closed (kept): no snapshot ⇒ cannot pass
    if self.voting_snapshot_total == 0 || self.validator_snapshot_total == 0 {
        return Some(ProposalState::Defeated);
    }
    let p = self.tier.params();
    // §6.2 stake quorum: voted stake (incl. abstain) ≥ quorum% of active stake
    let voted = self.for_votes + self.against_votes + self.abstain_votes;
    if voted.saturating_mul(100) < (p.stake_quorum_pct as u128) * (self.voting_snapshot_total as u128) {
        return Some(ProposalState::Defeated);
    }
    // §6.2 stake approval: yes / (yes+no) > approval%  (abstain excluded)
    let yes_no = self.for_votes + self.against_votes;
    let stake_ok = yes_no > 0
        && self.for_votes.saturating_mul(100) > (p.stake_approval_pct as u128) * yes_no;
    // §6.1 bicameral: stake chamber AND validator chamber (veto)
    if stake_ok && self.validator_chamber_approves() {
        Some(ProposalState::Passed)
    } else {
        Some(ProposalState::Defeated)
    }
}
```
`validator_chamber_approves()` is already correct (majority of the active set via
`validator_majority_pct`, fixed on #630) — it just needs `validator_snapshot_total` populated (§2)
and `CastValidatorVote` enabled (it already requires `validator_snapshot_total > 0`).

## 5. Open decisions (need owner/governance sign-off)
1. **Validator-set + stake source**: build a validator-staking module, or source from consensus
   (commonware) — and how execution reads it deterministically at a block.
2. **Unbonding inclusion** (§6.2): stakers in the 7-day unbonding queue at the snapshot still count.
3. **Delegation override** message + lane.
4. **`u64 → u128`** for the tally fields (codec + RPC + indexer impact; coordinate with the
   `tx-encoding` contract).
5. **Abstain** vote type (new ballot value + field).

## 6. Done-criteria
- Un-ignore `resolve_at_enforces_stake_quorum`; it passes (below-quorum ⇒ Defeated).
- Add: approval-threshold failure ⇒ Defeated; quorum-met + approval + validator-majority ⇒ Passed;
  unstaked voter weight 0 ⇒ rejected. Re-gate with `/marshal 630`.
