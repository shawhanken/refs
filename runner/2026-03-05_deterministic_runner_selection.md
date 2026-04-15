## 确定性 Runner Selection 算法说明

node/entitlement 分支和 runner/entitlement 分支已经实现

> 目标：在给定相同链上状态和随机种子的前提下，所有节点对同一任务得到**完全一致**的 Runner 委员会，同时保证公平性、抗女巫攻击与可复现性。

---

### 一、总体结构

确定性选择分两步：

1. **构造确定性的候选集**：从注册表中过滤出健康、满足能力与价格约束的 Runner，并按统一规则排序；
2. **基于种子的加权无放回选择**：用一个 32 字节种子驱动 Keccak，按质押权重做“Fisher-Yates 风格”的无放回抽样。

原先cip2中用的是环形索引，虽然也是确定性的，但是相关性太大了，所以有瑕疵。 现在我们加权无放回随机抽签等于是轮盘赌，只是权重更大的runner所对应的格子会更宽，这样就有更高概率中签。


只要：

- 链上 Runner Registry 状态一致；
- JobSpec（包含 job_id、verification 配置、max_price 等）一致；
- 区块高度 / VRF 输出一致；

那么所有节点的选择结果必然一致。

---

### 二、确定性候选集构造

#### 2.1 Registry 层过滤

在 `runner-registry` 中，`RunnerRegistryImpl::get_active_runners` 负责返回基础候选集：

- 只返回 `HealthStatus::Healthy` 的 Runner；
- 应用 `RunnerFilter`：
  - 最低声誉 `min_reputation`；
  - 支持的 `job_types`；
  - TEE 要求 `tee_required`；
  - 地域、region 限制等。

> 这里是“链上视角”的第一道过滤，保证只有健康、基础条件满足的 Runner 才参与后续选择。

#### 2.2 全局统一排序（关键的“确定性”保证）

过滤后，在 `runner-registry/src/registry.rs` 中对候选 Runner 做排序：

```rust
filtered_runners.sort_by_key(|r| r.address.as_bytes().to_vec());
```

即按 Runner 地址的原始字节序排序。

- 相同的 Registry 状态 → 相同的 Runner 集合；
- 此排序是纯函数（与本地哈希表顺序无关）；
- 所有节点在同一高度上看到的候选数组顺序完全一致。

这一点是后续使用随机种子进行“数组索引选择”时，保持全网一致的基础。

---

### 三、加权无放回随机选择（VRF-style）

选择逻辑位于 `runner/crates/job-dispatcher/src/selection.rs` 的 `RunnerSelector::vrf_select` 中。其输入为：

- 已排序好的 `candidates: &[RunnerRegistration]`；
- 需要的 Runner 数量 `count: u32`；
- 一个 32 字节种子 `seed: &[u8; 32]`（由 VRF 或 block randomness 派生）。

#### 3.1 stake → 权重：对数压缩，抗鲸鱼

首先把质押 `stake: U256` 转成整数权重：

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
    // weight = log2(ratio + 1) + 1，至少为 1
    let log = if ratio == 0 {
        0
    } else {
        u128::ilog2(ratio.saturating_add(1))
    } as u64;
    log.saturating_add(1)
}
```

特性：

- 质押低于基准的 Runner 被直接过滤（权重 0）；
- 质押翻很多倍时，权重只缓慢增加（对数压缩），防止单一大户完全垄断；
- 满足最低质押的 Runner 至少有权重 1，仍有被选中的机会。

构建“可选列表”：

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

> 注意这里再次对索引进行排序，确保加权选择是基于统一的顺序。

#### 3.2 种子驱动的加权“抽签” + 无放回

对每一次选择轮次 `round = 0..target-1`：

```rust
let total_weight: u64 = available.iter().map(|(_, w)| *w).sum();
if total_weight == 0 { break; }

// 使用 seed 和 round 推导出 [0, total_weight) 范围内的随机数 r
let mut hasher = Keccak256::new();
hasher.update(seed);
hasher.update(&round.to_le_bytes());
let hash = hasher.finalize();
let r = u64::from_le_bytes([
    hash[0], hash[1], hash[2], hash[3],
    hash[4], hash[5], hash[6], hash[7],
]) % total_weight;

// 在累积分布上找到 r 落入的权重区间
let mut cumulative = 0u64;
let mut chosen_idx = 0usize;
for (i, &(_, w)) in available.iter().enumerate() {
    cumulative = cumulative.saturating_add(w);
    if r < cumulative {
        chosen_idx = i;
        break;
    }
}

// 选中该 Runner 后，从 available 中移除 —— 无放回
let (runner_index, _) = available.remove(chosen_idx);
selected.push(candidates[runner_index].address);
```

这是一个 **“固定种子 + 加权轮盘赌 + 无放回”** 的过程：

- **固定性**：只要 `seed` 不变、候选集顺序不变、权重计算不变，则每一轮都得到同一个 `r`，落在同一个权重区间，因而选择同一个 Runner；
- **加权性**：权重越大，被选中的概率越高；
- **无放回性**：`available.remove(chosen_idx)` 保证每个 Runner 至多被选中一次。

最终返回前 `target = min(count, candidates.len())` 个选中的 Runner 地址：

```rust
selected
```

---

### 四、种子 `seed` 的来源（概要）

`RunnerSelector::select_committee` 的入参之一是 `vrf_seed: [u8; 32]`，其生成逻辑位于 `runner/crates/job-dispatcher/src/dispatcher.rs`：

```rust
let vrf_seed = generate_vrf_seed(&job_spec, current_block);
let runners = self.selector.select_committee(
    &job_spec,
    &self.registry,
    vrf_seed,
    current_block,
).await?;
```

当前版本中：

- `generate_vrf_seed` 使用 EC-VRF（带占位私钥）对 `job_id || current_block || submitter` 进行求值；
- 返回的 VRF 输出通过 `vrf_output_to_seed` 压缩为 32 字节种子。

未来演进方向（与分析文档一致）：

- 短期：改为纯 `block_hash` + HMAC/Keccak（去掉 dispatcher 私钥依赖），保持确定性同时减少中心化风险；
- 中期：在区块头中携带 EC-VRF 输出 `block_vrf_output`，用其作为更强随机性种子；
- 长期：阈值 BLS (threshold BLS VRF) 作为真正的无偏随机信标。

无论种子来自何处，一旦种子作为共识的一部分被固定，以上的选择过程就是**完全确定的纯函数**。

---

### 五、性质总结

- **全网确定性**：  
  候选集排序完全由地址决定，选择过程只依赖 `seed` 和候选集；在同一区块高度、同一 Job 下，所有节点必然得到相同的 Runner 列表。

- **公平性与抗女巫**：  
  质押越多、权重越大，被选中的概率越高，但使用对数压缩，避免极端鲸鱼垄断；同时，通过最低质押门槛过滤明显的女巫账户。

- **无放回、去相关**：  
  每轮选择后从 `available` 中删除对应 Runner，确保一次委员会内部无重复；相比简单“环形索引”方案，避免“相邻 Runner 总是一起被选中”的强相关性问题。

- **实现落地点清晰**：  
  - 候选集构造与排序：`runner-registry/src/registry.rs::get_active_runners`；  
  - 权重计算与无放回选择：`runner/crates/job-dispatcher/src/selection.rs::RunnerSelector::vrf_select`；  
  - 种子生成：`runner/crates/job-dispatcher/src/dispatcher.rs::generate_vrf_seed`。

