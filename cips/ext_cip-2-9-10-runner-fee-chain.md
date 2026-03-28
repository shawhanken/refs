# Runner 费用链路分析
## CIP-2 / CIP-9 / CIP-10 综合视角

**参考文档：** CIP-2（链下计算）、CIP-3（费用模型）、CIP-9（Runner 可挂载存储）、CIP-10（容器运行时）

---

## 一、三条费用流

```
Actor
  │
  ├── ① 链上 Gas (Cycles + Cells)   → 销毁/Validator tip
  ├── ② Runner 执行费 (CBY)          → Runner(s) + Aggregator
  └── ③ 存储费 (CBY)                 → Steamtrain 存储节点
```

这三条流**彼此独立**，分别结算。

---

## 二、完整时序

### Phase 0 — 基础设施准备（一次性/周期性）

| 操作 | 付款方 | 金额 | 收款方 |
|------|--------|------|--------|
| `VolumeCreate`（CIP-9 指令 40） | Actor | 5,000C + 500 Cells gas | 销毁 |
| 预付存储 escrow | Actor | CBY × 字节 × 周期 | 锁入 Volume Registry（地址 TBD；**0x09** 已分配给 **Governance**，CIP-9 延期实施） |
| `ContainerImageRegister`（CIP-10 指令 50） | 镜像注册人 | 10,000C + 200 Cells gas | 销毁 |

> 存储 escrow 不是一次性的，它是"余额驱动续存"：Steamtrain 节点定期从 escrow 中结算，余额耗尽则停止服务。

---

### Phase 1 — 作业准备

| 操作 | 付款方 | 金额 | 说明 |
|------|--------|------|------|
| `VolumeGrantAccess`（指令 41） | Actor | 3,000C + 150 Cells gas | 签发 CapToken 给目标 Runner |

> **CapToken 的时序问题**：CapToken 需要绑定具体 Runner 地址（`grantee`）。但 Runner 是 VRF 选出的，Actor 提前不知道是谁。实践中有两种方案：
> 1. Actor 提前与特定 Runner 协商（`required_runner_pool`），再签 CapToken；
> 2. Actor 先提交无卷挂载的 "probe job" 获得 Runner 地址，再签发 CapToken 重新提交（更贵但通用）。

---

### Phase 2 — 作业提交

Actor 调用 Job Dispatcher (0x02)，提交 `JobSpec`：

```rust
JobSpec {
    job_type: Container { spec: ContainerSpec },   // CIP-10
    bounds: ResourceBounds { ... },
    max_price: U256,      // Actor 愿意支付的 CBY 上限，锁入 Job Dispatcher 作 escrow
    tip: U256,            // 优先级加速费
    volume_mounts: [...], // CIP-9 CapToken 随 JobSpec 一起上链
    ...
}
```

| 发生了什么 | 说明 |
|-----------|------|
| Gas：JobSpec 字节计 Cells | `ContainerSpec` 的字节也计入 Cell 费用 |
| `max_price` CBY 冻结 | 锁入 Job Dispatcher，作业失败则退还 |
| `tip` CBY 冻结 | 优先级溢价，给聚合者/验证者 |
| 候选人过滤第 5 条 | `runner.RateCard 估价 ≤ max_price`，价格太高的 Runner 直接排除 |

---

### Phase 3 — VRF 选人 & Runner 执行

无链上费用发生。Runner 执行期间：

- 挂载 CIP-9 卷（链下，steamtrain-client 内部）
- 运行容器（Linux namespace + cgroup v2 资源受限）
- 卸载卷，获得 `manifest_root`

Runner 的成本（电费、带宽、硬件折旧）通过 Phase 4 的执行费覆盖。

---

### Phase 4 — 结果提交（Runner 付 Gas）

Runner 提交两笔交易（推荐同一 tx）：

| 指令 | 付款方 | Gas |
|------|--------|-----|
| `JobResultSubmit`（CIP-2） | Runner | 结果字节计 Cells + 基础 Cycles |
| `VolumeAnchorManifest`（CIP-9 指令 43）× N | Runner | 1,000C + 32 Cells × 每个写入卷 |

> Runner 提交时垫付 Gas，但这笔成本已经包含在它对 Actor 的报价（RateCard）里了。

---

### Phase 5 — 结果验证 & 费用结算

```
验证通过
    │
    ├── Runner(s) 收到执行费：
    │       MajorityVote/StructuredMatch → 多个 Runner 按规则分配 max_price
    │       EconomicBond / None         → 单 Runner 独得
    │
    ├── Aggregator 收到小额奖励 bonus（从 tip 或协议补贴中出）
    │
    └── 未参与/超时 Runner → reputation -= SLASH_THRESHOLD（不直接罚款，但影响后续被选概率）
```

```
验证失败 / 被质疑
    │
    ├── 作业回退，max_price CBY 退还 Actor
    ├── 质疑者提交质疑保证金 100 CBY
    ├── 质疑成功 → 肇事 Runner stake 被 slash，质疑者获保证金 + reward
    └── 质疑失败 → 质疑者的 100 CBY 销毁
```

---

## 三、费用汇总图

```
Actor
├── Gas(Cycles+Cells) ─────────────────────────────► 销毁（CIP-3 burn）
│
├── max_price (CBY) ──── Job Dispatcher escrow ─────► Runner(s) 执行费
│                                                      └── Aggregator bonus
│
├── tip (CBY) ──────────────────────────────────────► Aggregator / 优先处理
│
└── 存储 escrow (CBY) ── Volume Registry escrow ────► Steamtrain 存储节点
                                                        (CBY/byte/period 周期结算)

Runner（净收入 = 执行费 - 垫付Gas - 硬件成本）
└── VolumeAnchorManifest Gas ◄── Runner 垫付，含入报价

质疑者
└── 质疑保证金 100 CBY ──► 成功返还+奖励 / 失败销毁
```

---

## 四、各指令 Gas 费用速查

### CIP-9 卷操作

| 指令 | Cycles | Cells | 付款方 |
|------|--------|-------|--------|
| `VolumeCreate` | 5,000 | 500 | Actor |
| `VolumeGrantAccess` | 3,000 | 150 | Actor |
| `VolumeRevokeAccess` | 1,000 | 50 | Actor |
| `VolumeAnchorManifest` | 1,000 | 32 | Runner |
| `VolumeDelete` | 500 | 0 | Actor |
| `VolumeTransferOwnership` | 1,000 | 50 | Actor |

### CIP-10 镜像注册

| 指令 | Cycles | Cells | 付款方 |
|------|--------|-------|--------|
| `ContainerImageRegister` | 10,000 | 200 | 镜像注册人 |
| `ContainerImageRevoke` | 1,000 | 0 | 镜像注册人 |
| `ContainerImageSetPolicy` | 2,000 | 100 | 镜像注册人 |
| `ContainerImageReactivate` | 1,000 | 0 | 镜像注册人 |

---

## 五、关键设计哲学

**链上只管授权和完整性，定价走链下市场。**

- **Runner 执行费**：Actor 声明 `max_price` 上限，Runner 通过 `RateCard` 公示费率（CBY/秒、CBY/GiB·s），价格过滤在候选人构建时发生，最终价格由市场决定。
- **Steamtrain 存储费**：与 Runner 费完全解耦，由 Steamtrain 运营方独立公示，Actor 独立预付 escrow。
- **Gas（Cycles/Cells）**：链上操作成本，走 CIP-3 DualBasefee 机制，随链上负载动态调整。

三条流可以独立波动，互不影响对方的定价逻辑。这与白皮书 §17.7（Runner 市场链下定价）的核心哲学一致：**链上处理授权与完整性锚定，运营复杂度下沉到链下市场**。
