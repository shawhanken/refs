## Deterministic Runner Selection (Implementation Notes)

### 1. High-level structure

Deterministic selection is split into two steps:

1. **Build a deterministic candidate set**: filter runners from the registry by health, capabilities, and price constraints, then sort them with a canonical rule;
2. **Seeded, weighted sampling without replacement**: use a 32-byte seed to drive Keccak and perform a “Fisher-Yates–style” weighted sampling without replacement based on stake.

As long as:

- The on-chain Runner Registry state is identical;
- The `JobSpec` (including `job_id`, verification config, `max_price`, etc.) is identical;
- The block height / VRF output is identical;

then every node will compute the **same** runner selection result.

---

### 2. Deterministic candidate set construction

#### 2.1 Registry-level filtering

In `runner-registry`, `RunnerRegistryImpl::get_active_runners` builds the base candidate set:

- Only `HealthStatus::Healthy` runners are returned;
- It applies a `RunnerFilter`:
  - Minimum reputation `min_reputation`;
  - Supported `job_types`;
  - TEE requirement `tee_required`;
  - Region restrictions, etc.

> This is the **on-chain view** filtering step: only healthy runners satisfying basic invariants are allowed to enter the selection pipeline.

#### 2.2 Canonical global ordering (the key to determinism)

After filtering, `runner-registry/src/registry.rs` sorts the candidates:

```rust
filtered_runners.sort_by_key(|r| r.address.as_bytes().to_vec());
```

This sorts by the raw runner address bytes.

- Same registry state → same set of runners;
- This sort is a pure function (independent of any local hash map iteration order);
- All nodes at the same height see the candidate array in the **exact same order**.

This canonical ordering is the foundation for using an identical seed to pick indices and still getting identical results across the network.

---

### 3. Seeded weighted sampling without replacement (VRF-style)

The core selection logic lives in `runner/crates/job-dispatcher/src/selection.rs` in `RunnerSelector::vrf_select`. Inputs:

- Sorted candidates: `candidates: &[RunnerRegistration]`;
- Required runner count: `count: u32`;
- A 32-byte seed: `seed: &[u8; 32]` (derived from a VRF or block randomness).

#### 3.1 stake → weight: logarithmic compression, whale-resistant

First, convert each runner’s `stake: U256` into an integer weight:

```rust
const MIN_STAKE_WEIGHT_BASE: u128 = 10_000_000_000_000_000_000_000; // 10,000 CBY
let min_stake_u256 = U256::from(MIN_STAKE_WEIGHT_BASE);

fn stake_to_weight(stake: &U256, min_stake: &U256) -> u64 {
    if *stake < *min_stake {
        return 0;
    }
    let ratio = stake
        .checked_div(*min_stake)
        .unwrap_or_else(U256::zero)
        .as_u128();
    // weight = log2(ratio + 1) + 1, at least 1
    let log = if ratio == 0 {
        0
    } else {
        u128::ilog2(ratio.saturating_add(1))
    } as u64;
    log.saturating_add(1)
}
```

Properties:

- Runners with stake below the baseline are filtered out (weight = 0);
- Even if stake grows by orders of magnitude, the weight only grows slowly (logarithmically), preventing a single whale from completely dominating;
- Any runner meeting the minimum stake gets at least weight 1 and still has non-zero chance to be selected.

Build the “available” list:

```rust
let mut indices: Vec<usize> = (0..candidates.len()).collect();
indices.sort_by_key(|&i| candidates[i].address.as_bytes().to_vec());

let mut available: Vec<(usize, u64)> = indices
    .into_iter()
    .map(|idx| {
        let w = stake_to_weight(&candidates[idx].stake, &min_stake_u256);
        (idx, w)
    })
    .filter(|(_, w)| *w > 0)
    .collect();
```

> Note: we sort indices by address again to make sure the weighted selection is always applied over a canonical order.

#### 3.2 Seed-driven weighted “lottery” + no replacement

For each selection round `round = 0..target-1`:

```rust
let total_weight: u64 = available.iter().map(|(_, w)| *w).sum();
if total_weight == 0 { break; }

// Use seed and round to derive a pseudo-random r in [0, total_weight)
let mut hasher = Keccak256::new();
hasher.update(seed);
hasher.update(&round.to_le_bytes());
let hash = hasher.finalize();
let r = u64::from_le_bytes([
    hash[0], hash[1], hash[2], hash[3],
    hash[4], hash[5], hash[6], hash[7],
]) % total_weight;

// Walk the cumulative weights to find which interval r falls into
let mut cumulative = 0u64;
let mut chosen_idx = 0usize;
for (i, &(_, w)) in available.iter().enumerate() {
    cumulative = cumulative.saturating_add(w);
    if r < cumulative {
        chosen_idx = i;
        break;
    }
}

// Pick that runner, then remove it from `available` (no replacement)
let (runner_index, _) = available.remove(chosen_idx);
selected.push(candidates[runner_index].address);
```

Interpretation:

- Think of `[0, total_weight)` as partitioned into intervals:
  - Runner 0: `[0, w_0)`
  - Runner 1: `[w_0, w_0 + w_1)`
  - Runner 2: `[w_0 + w_1, w_0 + w_1 + w_2)`
  - …
- We draw a random point `r` in `[0, total_weight)`, and whichever interval it lands in is the chosen runner.

This yields a process that is:

- **Fixed / deterministic**: for a fixed `seed`, candidate order, and weight function, each `round` produces the same `r` and thus the same runner;
- **Weighted**: higher weight → larger interval → higher probability of being chosen;
- **Without replacement**: once a runner is chosen, it is removed from `available`, so it cannot be chosen again in this committee.

Finally, we return the first `target = min(count, candidates.len())` selected runners:

```rust
selected
```

---

### 4. Where does the seed come from? (Overview)

`RunnerSelector::select_committee` takes a `vrf_seed: [u8; 32]`, generated in `runner/crates/job-dispatcher/src/dispatcher.rs`:

```rust
let vrf_seed = generate_vrf_seed(&job_spec, current_block);
let runners = self.selector.select_committee(
    &job_spec,
    &self.registry,
    vrf_seed,
    current_block,
).await?;
```

In the current code:

- `generate_vrf_seed` uses an EC-VRF (with a placeholder secret key) on `job_id || current_block || submitter`;
- The VRF output is compressed via `vrf_output_to_seed` into a 32-byte seed.

Planned evolution (matching the analysis docs):

- **Short term**: switch to pure `block_hash` + HMAC/Keccak (remove the dispatcher private key dependency) while preserving determinism and reducing centralization risk;
- **Mid term**: include EC-VRF outputs in the block header (`block_vrf_output`) and use that as a stronger randomness seed;
- **Long term**: use threshold-BLS VRF as a true unbiased randomness beacon.

Regardless of the source, once the seed is part of consensus, the above selection algorithm is a **pure deterministic function**.

---

### 5. Summary of properties

- **Global determinism**  
  Candidate ordering is fully determined by address; selection depends only on `seed` and the candidate list. For a given block height and `JobSpec`, all nodes derive the same runner committee.

- **Fairness & Sybil resistance**  
  Runners with higher stake get larger weights and thus higher selection probability, but logarithmic compression prevents whales from completely dominating. The minimum-stake filter also eliminates obvious Sybil accounts.

- **No replacement & reduced correlation**  
  After each round the chosen runner is removed from `available`, so a single committee never contains duplicates. Compared to naive “ring indexing” approaches, this avoids pathological correlation (e.g., “adjacent runners are always selected together”).

- **Clear implementation touchpoints**  
  - Candidate construction & sorting: `runner-registry/src/registry.rs::get_active_runners`;  
  - Weight calculation & without-replacement selection: `runner/crates/job-dispatcher/src/selection.rs::RunnerSelector::vrf_select`;  
  - Seed generation: `runner/crates/job-dispatcher/src/dispatcher.rs::generate_vrf_seed`.

