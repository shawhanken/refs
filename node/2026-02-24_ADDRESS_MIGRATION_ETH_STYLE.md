# Ethereum-Style 地址迁移实施方案

> **状态**: 提案 (Proposal)
> **日期**: 2026-02-23
> **背景**: 白皮书定义了 Ethereum 风格地址，但代码实现使用了 Ed25519 (Solana 风格)。本文档分析现状，提出迁移方案及详细实施步骤。

---

## 目录

1. [背景与动机](#1-背景与动机)
2. [当前架构分析](#2-当前架构分析)
3. [迁移方案对比](#3-迁移方案对比)
4. [推荐方案：全量 Ethereum 风格迁移](#4-推荐方案全量-ethereum-风格迁移)
5. [详细实施计划](#5-详细实施计划)
6. [受影响文件清单](#6-受影响文件清单)
7. [数据迁移与兼容性](#7-数据迁移与兼容性)
8. [测试策略](#8-测试策略)
9. [风险评估](#9-风险评估)
10. [附录](#10-附录)
11. [PVM 执行层的地址迁移](#11-pvm-执行层的地址迁移)
12. [Runner 系统的地址迁移](#12-runner-系统的地址迁移)

---

## 1. 背景与动机

### 1.1 问题描述

白皮书一直使用 Ethereum 地址格式 (20 字节, secp256k1 派生), 但当前代码实现使用了 Ed25519 公钥 (32 字节) 作为地址。两者存在根本差异:

| 维度 | 白皮书 (Ethereum 风格) | 当前代码 (Ed25519) |
|------|----------------------|-------------------|
| 曲线 | secp256k1 | Ed25519 (Curve25519) |
| 公钥大小 | 33/65 字节 (压缩/非压缩) | 32 字节 |
| 地址大小 | 20 字节 | 32 字节 |
| 地址派生 | `keccak256(pubkey)[12..32]` | 直接使用公钥 |
| 签名格式 | ECDSA `(v, r, s)` | Ed25519 64 字节 |
| 钱包兼容 | MetaMask, WalletConnect | Phantom, Solflare |

### 1.2 战略优先级

根据客户反馈，当前核心优先级为:

1. **MetaMask + WalletConnect UX** — MetaMask 要求 EVM/secp256k1 语义
2. **Ethereum 资产桥接与流动性** — 当用户身份是 Ethereum 原生时，UX/信任/工具链体验最佳
3. **快速开发者采纳** — EVM 生态开发者工具最为成熟

### 1.3 核心结论

> 如果 "MetaMask/WalletConnect + ETH bridging" 是业务关键路径，应当现在就标准化为 Ethereum 风格地址，将代码向该模型迁移，而非削弱白皮书的定义。

---

## 2. 当前架构分析

### 2.1 密码学方案

**用户层**: Ed25519

```
types/src/consensus.rs:21
  pub type PublicKey = ed25519::PublicKey;  // 32 字节

types/src/execution.rs:7
  use commonware_cryptography::ed25519::{self, Batch, PublicKey, PrivateKey};
```

**共识层**: BLS12-381 (已与用户密钥解耦)

```
types/src/consensus.rs:14
  pub type Scheme = bls12381_threshold::Scheme<PublicKey, MinSig>;
```

这是好消息 — 共识层已经独立于用户地址/签名方案，迁移用户层不会影响共识。

### 2.2 地址格式

当前使用 32 字节 Ed25519 公钥作为地址，hex 编码 (64 个十六进制字符)，可选 `0x` 前缀:

```
cli/src/commands.rs:568
  println!("  Address: 0x{}", hex::encode(public_key.as_ref()));  // 64 hex chars
```

### 2.3 Transaction 签名

所有交易使用 Ed25519 签名, 带命名空间 `b"_COWBOY"`:

```rust
// types/src/execution.rs:28-44
pub struct Transaction {
    pub nonce: u64,
    pub instruction: Instruction,
    pub cycles_limit: u64,
    pub cells_limit: u64,
    pub max_fee_per_cycle: u64,
    pub max_fee_per_cell: u64,
    pub public: ed25519::PublicKey,          // <-- Ed25519
    pub signature: ed25519::Signature,       // <-- Ed25519
    pub additional_signers: Vec<(ed25519::PublicKey, ed25519::Signature)>,
    pub origin_tx_hash: Option<Digest>,
    // ...
}
```

签名验证:

```rust
// types/src/execution.rs:289
self.public.verify(NAMESPACE, &payload, &self.signature)
```

### 2.4 账户与 Actor 地址

**账户**: 以 `PublicKey` (Ed25519) 为键:

```rust
// types/src/execution.rs:1520-1528
pub enum Key {
    Account(PublicKey),                      // <-- 32 字节 Ed25519
    ActorStorage { actor: PublicKey, slot: Digest },
}
```

**Actor 地址派生**: CREATE2 风格但产生 Ed25519 公钥:

```rust
// types/src/execution.rs:1252-1278
pub fn derive_actor_address(creator: &PublicKey, salt: &[u8], code_hash: &Digest) -> PublicKey {
    let hash = sha256(creator || salt || code_hash);
    let seed = u64::from_be_bytes(hash[..8]);
    PrivateKey::from_seed(seed).public_key()   // <-- 产生 Ed25519 公钥
}
```

### 2.5 系统 Actor 地址

通过固定 u64 种子生成确定性 Ed25519 密钥对:

```rust
// runner/src/system_actors.rs:14-16
pub const RUNNER_REGISTRY_SEED: u64 = 0x0000000000000001;
pub fn runner_registry() -> PublicKey {
    PrivateKey::from_seed(Self::RUNNER_REGISTRY_SEED).public_key()
}
```

| 系统 Actor | Seed | 位置 |
|-----------|------|------|
| Runner Registry | `0x01` | `runner/src/system_actors.rs` |
| Job Dispatcher | `0x02` | `runner/src/system_actors.rs` |
| Result Verifier | `0x03` | `runner/src/system_actors.rs` |
| Secrets Manager | `0x04` | `runner/src/system_actors.rs` |
| TEE Verifier | `0x05` | `runner/src/system_actors.rs` |
| Token Registry | `0x06` | `token/src/address.rs` |

### 2.6 Token 存储键

存储键使用 32 字节公钥:

```rust
// token/src/storage_keys.rs:17
pub fn balance_key(owner: &PublicKey, token_id: &[u8; 32]) -> Vec<u8> {
    // "bal:" + owner(32B) + token_id(32B) = 68 bytes
}
```

### 2.7 Genesis 配置

支持 hex 公钥或 seed 两种方式:

```rust
// chain/src/genesis.rs:16-27
pub struct GenesisAccount {
    pub public_key_hex: Option<String>,  // hex 编码的 Ed25519 公钥
    pub seed: Option<u64>,               // 或通过 seed 生成
    pub balance: u64,
    pub nonce: u64,
}
```

---

## 3. 迁移方案对比

### 方案 A: 全量 Ethereum 风格迁移 (推荐)

将用户地址完全替换为 20 字节 Ethereum 地址 (secp256k1 + keccak256)。

| 维度 | 评分 |
|------|------|
| MetaMask 兼容性 | 原生支持 |
| ETH 桥接体验 | 最优 |
| 开发者采纳 | 最优 (EVM 工具链直接可用) |
| 实施成本 | 高 (全面修改) |
| 白皮书对齐 | 完全一致 |

### 方案 B: 双地址抽象层 (渐进)

引入 `Address` 枚举支持两种地址格式，逐步迁移。

```rust
pub enum Address {
    Ethereum([u8; 20]),  // 用户账户
    Internal([u8; 32]),  // 系统 Actor / 遗留
}
```

| 维度 | 评分 |
|------|------|
| MetaMask 兼容性 | 部分支持 |
| ETH 桥接体验 | 中等 |
| 开发者采纳 | 中等 (需理解双模式) |
| 实施成本 | 中等 (增量修改) |
| 白皮书对齐 | 部分一致 |
| 风险 | 长期维护两套方案的复杂度 |

### 方案 C: RPC 层适配 (最小改动)

保持内部 Ed25519 不变，在 RPC 层接受 EIP-155 交易并通过 `ecrecover` 映射到内部账户。

| 维度 | 评分 |
|------|------|
| MetaMask 兼容性 | 通过包装层支持 |
| ETH 桥接体验 | 较差 (链上规范地址不匹配) |
| 开发者采纳 | 较差 (本质是适配器) |
| 实施成本 | 低 |
| 白皮书对齐 | 不一致 |
| 风险 | 地址间接映射增加延迟和复杂度 |

### 方案选择矩阵

| 优先级 | 方案 A | 方案 B | 方案 C |
|--------|--------|--------|--------|
| MetaMask + WalletConnect | ★★★ | ★★☆ | ★☆☆ |
| ETH 资产桥接 | ★★★ | ★★☆ | ★☆☆ |
| 开发者采纳 | ★★★ | ★★☆ | ★☆☆ |
| 实施速度 | ★☆☆ | ★★☆ | ★★★ |
| 长期维护性 | ★★★ | ★☆☆ | ★★☆ |

**结论: 推荐方案 A**。虽然实施成本最高，但与白皮书完全对齐，长期维护成本最低，且在所有核心优先级上表现最优。

---

## 4. 推荐方案：全量 Ethereum 风格迁移

### 4.1 架构设计原则

1. **用户账户**: 20 字节 EVM 地址, secp256k1 签名, EIP-155 chain ID 语义
2. **共识/内部密钥**: 继续使用 Ed25519/BLS (验证者/节点内部)
3. **Actor/系统地址**: 统一为 20 字节规范方案, 不混用不同的地址派生方式

### 4.2 新类型定义

```rust
/// 20 字节 Ethereum 风格地址
#[derive(Clone, Copy, Hash, Eq, PartialEq, Ord, PartialOrd, Debug)]
pub struct Address([u8; 20]);

impl Address {
    pub const ZERO: Address = Address([0u8; 20]);

    /// 从 secp256k1 公钥派生地址: keccak256(pubkey[1..])[12..32]
    pub fn from_public_key(pubkey: &secp256k1::PublicKey) -> Self {
        let serialized = pubkey.serialize_uncompressed();
        let hash = keccak256(&serialized[1..]);  // 跳过 0x04 前缀
        let mut addr = [0u8; 20];
        addr.copy_from_slice(&hash[12..32]);
        Address(addr)
    }

    /// 从字节数组创建 (用于系统地址常量)
    pub const fn from_bytes(bytes: [u8; 20]) -> Self {
        Address(bytes)
    }

    /// EIP-55 checksum 编码
    pub fn to_checksum_string(&self) -> String {
        // 实现 EIP-55 mixed-case checksum
    }
}
```

### 4.3 新签名方案

```rust
/// secp256k1 ECDSA 签名 (EIP-155 兼容)
pub struct EthSignature {
    pub v: u8,       // recovery id + chain_id * 2 + 35
    pub r: [u8; 32],
    pub s: [u8; 32],
}

impl EthSignature {
    /// 从签名恢复地址 (ecrecover)
    pub fn recover_address(&self, message_hash: &[u8; 32]) -> Result<Address, Error> {
        // secp256k1 recovery -> public key -> keccak256 -> Address
    }
}
```

### 4.4 系统地址方案 (对照 EVM Precompile 惯例)

```rust
impl Address {
    /// 系统 Actor 使用低位地址 (类似 EVM precompile)
    pub const RUNNER_REGISTRY:  Address = Address::from_low_u64(0x01);
    pub const JOB_DISPATCHER:   Address = Address::from_low_u64(0x02);
    pub const RESULT_VERIFIER:  Address = Address::from_low_u64(0x03);
    pub const SECRETS_MANAGER:  Address = Address::from_low_u64(0x04);
    pub const TEE_VERIFIER:     Address = Address::from_low_u64(0x05);
    pub const TOKEN_REGISTRY:   Address = Address::from_low_u64(0x06);

    const fn from_low_u64(n: u64) -> Self {
        let mut bytes = [0u8; 20];
        let n_bytes = n.to_be_bytes();
        bytes[12] = n_bytes[0]; bytes[13] = n_bytes[1];
        bytes[14] = n_bytes[2]; bytes[15] = n_bytes[3];
        bytes[16] = n_bytes[4]; bytes[17] = n_bytes[5];
        bytes[18] = n_bytes[6]; bytes[19] = n_bytes[7];
        Address(bytes)
    }
}
```

### 4.5 Actor 地址派生 (Ethereum CREATE2)

```rust
/// 标准 Ethereum CREATE2 地址派生
pub fn derive_actor_address(
    deployer: &Address,
    salt: &[u8; 32],
    code_hash: &[u8; 32],
) -> Address {
    let mut input = Vec::with_capacity(1 + 20 + 32 + 32);
    input.push(0xff);
    input.extend_from_slice(deployer.as_ref());
    input.extend_from_slice(salt);
    input.extend_from_slice(code_hash);
    let hash = keccak256(&input);
    let mut addr = [0u8; 20];
    addr.copy_from_slice(&hash[12..32]);
    Address(addr)
}
```

---

## 5. 详细实施计划

### Phase 1: 基础设施 (Foundation)

> 目标: 添加依赖, 定义新类型, 不破坏现有代码

#### 1.1 添加 Cargo 依赖

在根 `Cargo.toml` 的 `[workspace.dependencies]` 中添加:

```toml
k256 = { version = "0.13", features = ["ecdsa", "ecdsa-core"] }
sha3 = "0.10"          # keccak256
alloy-primitives = "0.8"  # 可选, 提供 Address, B256 等 EVM 原语
```

#### 1.2 定义 Address 类型

**文件**: `types/src/address.rs` (新建)

定义 `Address` 结构体:
- `[u8; 20]` 内部表示
- 实现 `Write`, `Read`, `EncodeSize`, `Hash`, `Eq`, `Ord` 等 trait
- 实现 `Display` (EIP-55 checksum)
- 实现 `FromStr` (解析 `0x` 前缀 hex, 验证 checksum)
- 实现 `from_public_key()` 通过 keccak256 从 secp256k1 公钥派生
- 定义系统 Actor 常量地址

#### 1.3 定义 EthSignature 类型

**文件**: `types/src/signature.rs` (新建)

定义签名结构体:
- `v`, `r`, `s` 字段
- `recover_address()` 方法
- `sign()` 方法
- 实现 `Write`, `Read`, `EncodeSize` trait

#### 1.4 更新 lib.rs 导出

**文件**: `types/src/lib.rs`

添加新模块和类型导出。

### Phase 2: 核心类型替换 (Core Swap)

> 目标: 将所有用户面的 Ed25519 引用替换为 secp256k1 + Address

#### 2.1 Transaction 结构体

**文件**: `types/src/execution.rs`

**Before:**
```rust
pub struct Transaction {
    // ...
    pub public: ed25519::PublicKey,
    pub signature: ed25519::Signature,
    pub additional_signers: Vec<(ed25519::PublicKey, ed25519::Signature)>,
}
```

**After:**
```rust
pub struct Transaction {
    // ...
    pub from: Address,                // 发送者地址 (20 字节)
    pub signature: EthSignature,      // ECDSA (v, r, s)
    pub additional_signers: Vec<(Address, EthSignature)>,
}
```

关键方法修改:

| 方法 | 修改内容 |
|------|---------|
| `sign()` | 使用 secp256k1 私钥签名, keccak256 哈希 |
| `verify()` | 使用 `ecrecover` 恢复地址并比对 `self.from` |
| `verify_batch()` | 重写为逐个验证 (secp256k1 无原生 batch verify) |
| `payload()` | 使用 keccak256 替代 SHA256 |
| `digest()` | 使用 keccak256 |
| `sign_multi()` | 适配新签名类型 |
| `create_deferred()` | `sender` 参数类型改为 `Address` |
| `Write/Read/EncodeSize` | 适配新字段大小 |

#### 2.2 Account 与 Key 枚举

**文件**: `types/src/execution.rs`

```rust
// Before:
pub enum Key {
    Account(PublicKey),              // 32 字节 Ed25519
    ActorStorage { actor: PublicKey, slot: Digest },
}

// After:
pub enum Key {
    Account(Address),               // 20 字节 Ethereum
    ActorStorage { actor: Address, slot: Digest },
}
```

同时修改:
- `Key::compute_actor_storage_slot()` — 参数从 `&PublicKey` 改为 `&Address`
- `Key::actor_storage()` 和 `Key::actor_storage_from_key()` — 同上
- `Write`/`Read` 实现 — 适配 20 字节

#### 2.3 Actor 结构体

**文件**: `types/src/execution.rs`

```rust
// Before:
pub struct Actor {
    pub address: PublicKey,   // 32 字节 Ed25519
    // ...
}

// After:
pub struct Actor {
    pub address: Address,     // 20 字节 Ethereum
    // ...
}
```

#### 2.4 derive_actor_address()

**文件**: `types/src/execution.rs`

从 Ed25519 seed 派生改为 Ethereum CREATE2:

```rust
// Before: sha256 -> seed -> Ed25519 key pair
// After:  keccak256(0xff || deployer || salt || code_hash) -> 截取后 20 字节
```

#### 2.5 Instruction 中的地址字段

**文件**: `types/src/execution.rs`

涉及 `PublicKey` 引用的 instruction 需要替换:

```rust
// SystemInstruction
CreateAccount { account: Address },           // was PublicKey
Transfer { to: Address, amount: u64 },        // was PublicKey
RunnerUpdateRateCard { runner: Address, .. },  // was PublicKey
RunnerHeartbeat { runner: Address },           // was PublicKey
RunnerDeregister { runner: Address },          // was PublicKey
TokenTransfer { to: Address, .. },            // was PublicKey
TokenTransferFrom { from: Address, to: Address, .. },
TokenApprove { spender: Address, .. },        // was PublicKey
TokenMint { to: Address, .. },
TokenBurn { from: Address, .. },
TokenFreeze { account: Address, .. },
TokenUnfreeze { account: Address, .. },
TokenSetHook { hook_address: Option<Address>, .. },
TokenTransferOwnership { new_owner: Address, .. },
// ...
```

#### 2.6 Message 结构体

**文件**: `types/src/execution.rs`

```rust
// Message 中的地址字段也需要替换
pub struct Message {
    pub sender: Address,     // was PublicKey
    pub target: Address,     // was PublicKey
    // ...
}
```

### Phase 3: 系统 Actor 与 Token

#### 3.1 系统 Actor 地址

**文件**: `runner/src/system_actors.rs`

```rust
// Before:
pub fn runner_registry() -> PublicKey {
    PrivateKey::from_seed(0x01).public_key()  // 32 字节
}

// After:
pub const RUNNER_REGISTRY: Address = Address::from_low_u64(0x01);  // 20 字节常量
```

所有系统 Actor 改为 `const Address` 常量，不再需要运行时函数调用。

**文件**: `token/src/address.rs`

```rust
// Before:
pub fn token_registry_address() -> PublicKey {
    PrivateKey::from_seed(0x06).public_key()
}

// After:
pub const TOKEN_REGISTRY_ADDRESS: Address = Address::from_low_u64(0x06);
```

#### 3.2 Token 存储键

**文件**: `token/src/storage_keys.rs`

所有存储键函数的参数从 `&PublicKey` (32 字节) 改为 `&Address` (20 字节):

```rust
// Before:
pub fn balance_key(owner: &PublicKey, token_id: &[u8; 32]) -> Vec<u8> {
    // "bal:" + 32B + 32B = 68 bytes

// After:
pub fn balance_key(owner: &Address, token_id: &[u8; 32]) -> Vec<u8> {
    // "bal:" + 20B + 32B = 56 bytes
```

**注意**: 这会改变存储键的二进制布局。如果已有链上数据，需要数据迁移 (见第 7 节)。

#### 3.3 Token 核心逻辑

**文件**: `chain/src/token/core.rs`, `chain/src/token/admin.rs`

所有使用 `PublicKey` 的 Token 操作逻辑需要改为 `Address`。

### Phase 4: 外部接口

#### 4.1 CLI 钱包

**文件**: `cli/src/commands.rs`

**密钥生成**:
```rust
// Before:
let private_key = PrivateKey::random(&mut OsRng);  // Ed25519
let public_key = private_key.public_key();
println!("  Address: 0x{}", hex::encode(public_key.as_ref()));  // 64 hex chars

// After:
let signing_key = k256::ecdsa::SigningKey::random(&mut OsRng);  // secp256k1
let verifying_key = signing_key.verifying_key();
let address = Address::from_public_key(verifying_key);
println!("  Address: {}", address.to_checksum_string());  // 0x + 40 hex chars (EIP-55)
```

**私钥存储**:
- 格式从 32 字节 (Ed25519 seed) 改为 32 字节 (secp256k1 标量)
- 保持 hex 编码文件格式不变
- `discover_private_key()` 需要返回 secp256k1 私钥类型

**地址解析**:
```rust
// parse_public_key() -> parse_address()
// 接受 0x 前缀的 40 字符 hex 或 EIP-55 checksum
```

#### 4.2 RPC API

**文件**: `chain/src/rpc.rs`

主要改动:
- 所有 API 响应中的地址使用 EIP-55 checksum 格式 (40 hex chars + `0x`)
- 交易提交端点接受 EIP-155 格式的签名交易
- Account 查询端点 URL 路径从 64 char hex 改为 40 char hex
- 添加 `eth_chainId` 等 JSON-RPC 兼容端点 (可选, 用于 MetaMask 兼容)

#### 4.3 Runner 类型序列化

**文件**: `runner/src/types.rs`

所有 `hex::encode(public_key.as_ref())` 调用需要改为使用 `Address::to_checksum_string()` 或 `hex::encode(address.as_ref())`。

#### 4.4 Genesis 配置

**文件**: `chain/src/genesis.rs`

```rust
// Before:
pub struct GenesisAccount {
    pub public_key_hex: Option<String>,  // Ed25519 公钥 hex
    pub seed: Option<u64>,
    // ...
}

// After:
pub struct GenesisAccount {
    pub address: Option<String>,     // Ethereum 地址 (0x + 40 hex)
    pub private_key: Option<String>, // secp256k1 私钥 (可选, 用于测试)
    // ...
}
```

### Phase 5: 共识层保持不变

共识层已使用 BLS12-381 (`types/src/consensus.rs`), 验证者身份可以继续使用 Ed25519。

**唯一需要改的点**: `consensus.rs:21` 的 `pub type PublicKey` — 目前全局复用为 `ed25519::PublicKey`, 用于账户地址和验证者身份。迁移后:

```rust
// 验证者身份继续使用 Ed25519
pub type ValidatorKey = ed25519::PublicKey;

// 不再在 consensus.rs 导出 PublicKey 给用户层使用
// 用户地址使用 types/src/address.rs 中的 Address
```

---

## 6. 受影响文件清单

### 6.1 必须修改的文件

| 文件 | 修改范围 | 优先级 |
|------|---------|--------|
| `types/src/address.rs` | **新建** — Address 类型定义 | P0 |
| `types/src/signature.rs` | **新建** — EthSignature 类型定义 | P0 |
| `types/src/execution.rs` | Transaction, Account, Actor, Key, Instruction, Message, derive_actor_address — 全面修改 | P0 |
| `types/src/consensus.rs` | PublicKey type alias 拆分 | P0 |
| `types/src/lib.rs` | 新模块导出 | P0 |
| `runner/src/system_actors.rs` | 系统 Actor 地址改为常量 | P1 |
| `token/src/address.rs` | Token Registry 地址改为常量 | P1 |
| `token/src/storage_keys.rs` | 存储键参数类型 32B→20B | P1 |
| `chain/src/execution.rs` | 执行引擎中所有地址引用 | P1 |
| `chain/src/genesis.rs` | Genesis 配置格式 | P1 |
| `chain/src/rpc.rs` | API 地址格式, 交易提交 | P1 |
| `chain/src/token/core.rs` | Token 操作地址类型 | P1 |
| `chain/src/token/admin.rs` | Token 管理地址类型 | P1 |
| `cli/src/commands.rs` | 钱包生成, 地址解析, 交易签名 | P2 |
| `runner/src/types.rs` | 序列化中的地址格式 | P2 |

### 6.2 PVM 执行层必须修改的文件

| 文件 | 修改内容 | 优先级 |
|------|---------|--------|
| `pvm/crates/pvm-host/src/lib.rs` | `HostContext` 字段大小 (sender/actor_addr: 32→20B)；所有地址参数注释更新 | P1 |
| `chain/src/pvm_host.rs` | `PvmExecutionContext.actor_address`, `.sender` 类型；`send_message` 验证 (32→20)；timer ID 派生；token 请求负载编码；`submit_job` 地址获取 | P1 |
| `chain/src/pvm_executor.rs` | `PvmExecutionContext::new()` 参数类型 | P1 |
| `pvm/crates/pvm-runtime/src/module.rs` | Python 模块绑定：地址相关参数验证长度 | P2 |

### 6.3 Runner 系统必须修改的文件

| 文件 | 修改内容 | 优先级 |
|------|---------|--------|
| `runner/src/types.rs` | `RunnerRegistration.address/public_key`、`JobSpec.submitter`、`RunnerResult.runner` 类型；序列化 hex 格式 | P1 |
| `runner/src/storage_keys.rs` | 所有 `&PublicKey` 参数改为 `&Address`；键长度变化 | P1 |
| `chain/src/runner/registry.rs` | 地址类型适配；活跃列表格式；heartbeat/deregister | P1 |
| `chain/src/runner/dispatcher.rs` | submitter 地址；committee 选择返回类型 | P1 |
| `chain/src/runner/verifier.rs` | runner 地址；签名验证 (Ed25519 → ecrecover) | P1 |
| `chain/src/rpc.rs` | Runner RPC 端点：地址解析 (64→40 chars)；消息签名构造；ecrecover 验证 | P2 |

### 6.4 可能受影响的文件

| 文件 | 原因 |
|------|------|
| `chain/src/mempool.rs` | 交易验证 |
| `storage/src/lib.rs` | 存储层 Key 类型 |
| 所有测试文件 | 测试中硬编码的 Ed25519 密钥对和地址 |
| Actor Python 示例代码 | `ctx["sender"]`/`ctx["actor_addr"]` 长度假设；`_addr()` 辅助函数 |

### 6.3 不需要修改的文件

| 文件 | 原因 |
|------|------|
| 共识协议核心代码 | 使用 BLS12-381, 已独立 |
| P2P 网络层 | 使用 Ed25519 peer identity, 可保持不变 |

---

## 7. 数据迁移与兼容性

### 7.1 链上状态迁移

如果已有测试网/开发网数据, 需要考虑:

| 数据 | 影响 | 方案 |
|------|------|------|
| 账户余额 | Key 从 32B→20B, 需重新映射 | Genesis 重置或状态迁移脚本 |
| Token 余额 | 存储键包含 32B 地址, 需重建 | Genesis 重置 |
| Actor 存储 | Actor 地址格式变化 | 重新部署 |
| 交易历史 | 签名格式不兼容 | 历史数据保留但标记为 legacy |

**建议**: 在主网上线前完成迁移, 测试网/开发网可直接 Genesis 重置。

### 7.2 Wire Protocol 兼容

- 交易二进制编码格式会发生变化 (地址 32→20 字节, 签名 64→65 字节)
- 需要增加协议版本号或在 Genesis 中标记
- 现有节点需要同时升级

### 7.3 SDK/客户端兼容

- 现有 CLI 工具的私钥文件格式会变化
- 需要提供密钥迁移工具或明确标注 breaking change
- 文档需同步更新

---

## 8. 测试策略

### 8.1 单元测试

| 测试类别 | 内容 |
|---------|------|
| Address 类型 | `from_public_key()`, EIP-55 编码/解码, `from_bytes()`, 序列化/反序列化 |
| EthSignature | 签名, 验证, `ecrecover`, 重放保护 |
| Transaction | sign/verify 往返, multi-sig, deferred tx |
| Key 枚举 | Account(Address) 序列化, ActorStorage 序列化 |
| Actor 派生 | CREATE2 地址确定性, 不同输入产生不同地址 |
| 系统地址 | 常量值验证, 不与用户地址冲突 |
| Token 存储键 | 新键格式 (20B 地址), 长度验证 |

### 8.2 集成测试

| 测试类别 | 内容 |
|---------|------|
| 端到端交易 | secp256k1 签名 → 提交 → 执行 → 验证 |
| Genesis 初始化 | 新格式 genesis 配置加载 |
| Token 操作 | CIP-20 全流程 (create, transfer, approve 等) |
| Actor 部署 | CREATE2 地址派生 + 执行 |
| RPC API | 地址格式验证 (EIP-55) |

### 8.3 PVM 层测试

| 测试类别 | 内容 |
|---------|------|
| context() 地址格式 | `sender` 和 `actor_addr` 均为 20 字节 |
| send_message 验证 | 20 字节地址通过；32 字节拒绝 (`InvalidInput`) |
| token host 函数 | `to`/`from_`/`spender` 20 字节验证；旧 32 字节拒绝 |
| submit_job | 消息正确路由到 20 字节 Job Dispatcher 地址 |
| timer ID 派生 | 同 actor 在迁移前后 timer ID 不同 (预期行为) |
| Python actor 端到端 | 更新后的 actor 代码能正常运行；旧代码 `_addr()` 报错 |
| token 请求负载 | 编码/解码往返，地址部分 20 字节 |

### 8.4 Runner 层测试

| 测试类别 | 内容 |
|---------|------|
| Runner 注册 | secp256k1 密钥对注册，地址正确派生 |
| Runner 心跳 | 20 字节地址 RPC 路径解析 |
| 结果签名与验证 | `ecrecover` 恢复地址 == `runner_address` |
| 存储键格式 | `runner:{20B}` 键正确写入/读取 |
| Job 派发 | `submitter` 20 字节地址正确存储 |
| 共识阈值 | `RunnerResult.runner` 20 字节比较 |
| 活跃 Runner 列表 | 地址序列化为 0x + 40 chars |

### 8.5 兼容性测试

| 测试类别 | 内容 |
|---------|------|
| MetaMask 签名 | 使用 MetaMask 签名的交易能被正确验证 |
| EIP-155 重放保护 | chain ID 不同时签名无效 |
| WalletConnect | 通过 WalletConnect 提交交易 |

---

## 9. 风险评估

### 9.1 高风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 全面代码修改导致回归 | 功能中断 | 分阶段实施, 每个 Phase 后全面测试 |
| secp256k1 性能差异 | secp256k1 签名验证比 Ed25519 慢约 5x | 可接受 — 以太坊每秒处理数千笔交易验证 |
| 存储键格式变化 | 链上数据不兼容 | 在主网前完成, 测试网 genesis 重置 |

### 9.2 中风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Batch verify 不可用 | secp256k1 无原生 batch verify | 可用 `rayon` 并行验证, 或使用 `k256` 的 batch API |
| 多签方案变化 | 现有多签逻辑需适配 | 保持相同逻辑, 仅替换密码学原语 |
| 依赖审计 | 新增 `k256`, `sha3` 依赖 | 使用 RustCrypto 生态, 审计成熟 |

### 9.3 低风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Ed25519 节点身份 | P2P 层使用 Ed25519 | 不受影响, 保持不变 |
| BLS 共识 | 共识层使用 BLS12-381 | 不受影响, 已解耦 |

---

## 10. 附录

### 10.1 关键密码学对比

| 特性 | Ed25519 | secp256k1 (ECDSA) |
|------|---------|-------------------|
| 安全级别 | ~128 bit | ~128 bit |
| 私钥大小 | 32 字节 | 32 字节 |
| 公钥大小 | 32 字节 | 33 字节 (压缩) / 65 字节 (非压缩) |
| 签名大小 | 64 字节 | 65 字节 (含 recovery id) |
| 地址大小 | 32 字节 (=公钥) | 20 字节 (keccak256 截断) |
| 签名速度 | ~15,000/s | ~5,000/s |
| 验证速度 | ~7,000/s | ~3,000/s |
| Batch 验证 | 支持 (线性加速) | 不原生支持 |
| 密钥恢复 | 不支持 | 支持 (ecrecover) |

### 10.2 推荐 Rust Crate

| 用途 | Crate | 版本 | 说明 |
|------|-------|------|------|
| secp256k1 椭圆曲线 | `k256` | 0.13+ | RustCrypto 生态, 纯 Rust, 支持 ECDSA |
| Keccak-256 哈希 | `sha3` | 0.10+ | RustCrypto 生态 |
| EVM 基础类型 (可选) | `alloy-primitives` | 0.8+ | 提供 `Address`, `B256`, EIP-55 等 |
| 高性能替代 (可选) | `libsecp256k1` | 0.7+ | 基于 Bitcoin 的 C 库绑定, 更快 |

### 10.3 EIP-155 交易签名流程

```
1. 构造交易数据: [nonce, instruction, cycles_limit, cells_limit, ...]
2. 附加 chain_id: data || chain_id || 0 || 0
3. 哈希: message_hash = keccak256(data_with_chain_id)
4. 签名: (r, s, v) = secp256k1_sign(private_key, message_hash)
5. v = recovery_id + chain_id * 2 + 35
```

### 10.4 ecrecover 验证流程

```
1. 从交易中提取 signature (v, r, s) 和 message_hash
2. recovery_id = (v - 35) - chain_id * 2  (or v - 27 for legacy)
3. public_key = secp256k1_recover(message_hash, r, s, recovery_id)
4. address = keccak256(public_key[1..])[12..32]
5. 验证: address == transaction.from
```

### 10.5 实施时间线估算

| Phase | 描述 | 预估工时 | 依赖 |
|-------|------|---------|------|
| Phase 1 | 基础设施 (新类型定义) | 2-3 天 | 无 |
| Phase 2 | 核心类型替换 | 5-7 天 | Phase 1 |
| Phase 3 | 系统 Actor + Token | 3-4 天 | Phase 2 |
| Phase 4 | 外部接口 (CLI, RPC) | 3-4 天 | Phase 2 |
| Phase 5 | PVM + Runner 适配 | 4-5 天 | Phase 2, 3 |
| Phase 6 | 测试 + 调试 | 3-5 天 | Phase 3, 4, 5 |
| **合计** | | **20-28 天** | |

---

## 11. PVM 执行层的地址迁移

> 本节专门描述 PVM (Python 虚拟机) 执行层与地址迁移相关的全部改动。PVM 涉及 Rust ↔ Python 边界，地址变化会同时影响 Rust 侧的 Host API 实现和 Python 侧的 Actor 合约接口。

### 11.1 当前 PVM 地址架构

**核心问题**: 地址在 Rust/Python 边界以 `Vec<u8>` (原始字节) 传递，长度硬编码为 **32 字节**。

**涉及文件:**

| 文件 | 当前地址处理 |
|------|------------|
| `pvm/crates/pvm-host/src/lib.rs` | `HostApi` trait，地址参数为 `&[u8]`，注释说明"32-byte address" |
| `chain/src/pvm_host.rs` | `PvmExecutionContext` 结构体，`CowboyHost` 实现 |
| `pvm/crates/pvm-runtime/src/module.rs` | Python 模块绑定，地址作为 `bytes` 传入 Python |
| `chain/src/pvm_executor.rs` | 主执行入口，构造 `PvmExecutionContext` |

**PvmExecutionContext 中的地址字段** (`chain/src/pvm_host.rs:280-339`):

```rust
pub struct PvmExecutionContext<'a, S: StateStore> {
    pub actor_address: PublicKey,    // 32 字节 Ed25519 — Actor 自身地址
    pub sender: PublicKey,           // 32 字节 Ed25519 — 交易发送者
    // Token 请求负载中的地址也是 32 字节嵌入:
    // token_transfer_requests: token_id(32) || to(32) || amount(8)
    // token_approve_requests:  token_id(32) || spender(32) || amount(8)
    // ...
}
```

**`send_message` 的地址验证** (`chain/src/pvm_host.rs:658-661`):

```rust
if target.len() != 32 {
    return Err(HostError::InvalidInput);
}
```

**Python 侧的地址约定** (`examples/token/demo_pvm_token_host.py`):

```python
def _addr(b):
    """Ensure 32-byte address."""
    if isinstance(b, bytes) and len(b) == 32:
        return b
    raise ValueError("address must be 32 bytes")
```

**计时器 ID 派生**，使用 actor_address 作为熵 (`chain/src/pvm_host.rs:682`):

```rust
hasher.update(self.ctx.actor_address.as_ref());  // 32 字节参与哈希
```

### 11.2 PVM 地址迁移所需改动

#### 11.2.1 PvmExecutionContext 字段类型

**文件**: `chain/src/pvm_host.rs`

```rust
// Before:
pub struct PvmExecutionContext<'a, S: StateStore> {
    pub actor_address: PublicKey,   // ed25519::PublicKey (32 字节)
    pub sender: PublicKey,          // ed25519::PublicKey (32 字节)
    // ...
}

// After:
pub struct PvmExecutionContext<'a, S: StateStore> {
    pub actor_address: Address,     // [u8; 20] Ethereum 地址
    pub sender: Address,            // [u8; 20] Ethereum 地址
    // ...
}
```

同步修改 `PvmExecutionContext::new()` 的参数类型。

#### 11.2.2 HostContext — Python 可见的上下文

**文件**: `pvm/crates/pvm-host/src/lib.rs`

```rust
// Before:
pub struct HostContext {
    pub sender: Bytes,      // 32 字节 Ed25519 公钥
    pub actor_addr: Bytes,  // 32 字节 Ed25519 公钥
    // ...
}

// After:
pub struct HostContext {
    pub sender: Bytes,      // 20 字节 Ethereum 地址
    pub actor_addr: Bytes,  // 20 字节 Ethereum 地址
    // ...
}
```

**注意**: `HostContext` 的字段类型 (`Bytes = Vec<u8>`) 不变，变化的是内容长度：**32 → 20 字节**。这是一个 **breaking change**，所有现有 Python Actor 代码中的地址处理逻辑都需要更新。

#### 11.2.3 HostApi Trait — 地址参数注释更新

**文件**: `pvm/crates/pvm-host/src/lib.rs`

`HostApi` trait 中所有涉及地址的参数目前注释为 "32-byte address"，需要更新为 "20-byte address"，并确保实现侧的验证逻辑对应修改:

```rust
// Before:
/// Transfer tokens from the calling actor to recipient. to: 32-byte address.
fn token_transfer(&mut self, token_id: &[u8; 32], to: &[u8], amount: u64) -> HostResult<()>;

// After:
/// Transfer tokens from the calling actor to recipient. to: 20-byte Ethereum address.
fn token_transfer(&mut self, token_id: &[u8; 32], to: &[u8], amount: u64) -> HostResult<()>;
```

实现侧 (`chain/src/pvm_host.rs`) 中需要增加 **20 字节**验证:

```rust
// token_transfer 实现中:
if to.len() != 20 {
    return Err(HostError::InvalidInput);
}
```

#### 11.2.4 send_message 地址验证

**文件**: `chain/src/pvm_host.rs:658-661`

```rust
// Before:
if target.len() != 32 {
    return Err(HostError::InvalidInput);
}

// After:
if target.len() != 20 {
    return Err(HostError::InvalidInput);
}
```

#### 11.2.5 Timer ID 派生

**文件**: `chain/src/pvm_host.rs:682`

计时器 ID 的派生使用了 `actor_address`，字段类型改变后需要适配:

```rust
// Before:
hasher.update(self.ctx.actor_address.as_ref());  // PublicKey.as_ref() = 32 bytes

// After:
hasher.update(self.ctx.actor_address.as_ref());  // Address.as_ref() = 20 bytes
```

逻辑不变，仅输入长度变化，但会导致**相同 actor 的 timer ID 生成结果不同** — 若链上有历史计时器数据，需要处理兼容性。

#### 11.2.6 Token 请求负载中的地址编码

`PvmExecutionContext` 中的 token 请求使用二进制序列化，嵌入了地址字节:

```
// Before:
token_transfer_requests: token_id(32B) || to(32B) || amount(8B) = 72 bytes

// After:
token_transfer_requests: token_id(32B) || to(20B) || amount(8B) = 60 bytes
```

涉及所有 token 请求的编码/解码逻辑:
- `token_transfer_requests` — `to` 字段 32→20
- `token_transfer_from_requests` — `from` + `to` 各 32→20
- `token_approve_requests` — `spender` 字段 32→20
- `token_mint_requests` — `to` 字段 32→20

**文件**: `chain/src/pvm_host.rs` 中各 token host 函数的编码逻辑，以及 `chain/src/execution.rs` 中对应的解码逻辑。

#### 11.2.7 submit_job 中系统地址获取

**文件**: `chain/src/pvm_host.rs:710-712`

```rust
// Before:
fn submit_job(&mut self, job_spec: &[u8]) -> HostResult<()> {
    let dispatcher = SystemActorAddresses::job_dispatcher();  // 返回 PublicKey (32B)
    self.send_message(dispatcher.as_ref(), job_spec)          // as_ref() = 32 bytes
}

// After:
fn submit_job(&mut self, job_spec: &[u8]) -> HostResult<()> {
    let dispatcher = Address::JOB_DISPATCHER;  // 常量 [u8; 20]
    self.send_message(dispatcher.as_ref(), job_spec)  // as_ref() = 20 bytes
}
```

### 11.3 Python Actor 合约接口变化 (Breaking Change)

这是对 **Actor 开发者**影响最大的部分。所有 Actor Python 代码中与地址相关的逻辑都需要更新。

#### 11.3.1 context() 返回值变化

```python
# Before:
ctx = pvm_host.context()
sender = ctx["sender"]      # bytes, len == 32
actor_addr = ctx["actor_addr"]  # bytes, len == 32

# After:
ctx = pvm_host.context()
sender = ctx["sender"]      # bytes, len == 20
actor_addr = ctx["actor_addr"]  # bytes, len == 20
```

#### 11.3.2 地址验证辅助函数

现有 Python 代码中的 `_addr()` 辅助函数需要更新:

```python
# Before:
def _addr(b):
    if isinstance(b, bytes) and len(b) == 32:
        return b
    raise ValueError("address must be 32 bytes")

# After:
def _addr(b):
    if isinstance(b, bytes) and len(b) == 20:
        return b
    raise ValueError("address must be 20 bytes (Ethereum address)")

# 可选: 添加 hex 格式支持 (0x + 40 chars)
def _addr_from_hex(s: str) -> bytes:
    s = s.lower().removeprefix("0x")
    if len(s) != 40:
        raise ValueError("Ethereum address must be 40 hex chars")
    return bytes.fromhex(s)
```

#### 11.3.3 send_message 目标地址

```python
# Before:
pvm_host.send_message(target_32bytes, payload)

# After:
pvm_host.send_message(target_20bytes, payload)
```

#### 11.3.4 Token 函数中的地址参数

所有 token 函数的 `to`, `from_`, `spender`, `owner` 等参数从 32 字节改为 20 字节:

```python
# Before:
pvm_host.token_transfer(token_id, to_32bytes, amount)
pvm_host.token_approve(token_id, spender_32bytes, amount)
pvm_host.token_balance_of(token_id, owner_32bytes)

# After:
pvm_host.token_transfer(token_id, to_20bytes, amount)
pvm_host.token_approve(token_id, spender_20bytes, amount)
pvm_host.token_balance_of(token_id, owner_20bytes)
```

#### 11.3.5 Python SDK 层建议

建议提供官方 Python 辅助库 (可通过 PVM stdlib 内置)，封装地址处理:

```python
# 建议提供 cowboy_sdk.py (通过 stdlib 或 actor 模板注入)
class Address:
    """Ethereum-style 20-byte address helper."""

    def __init__(self, raw: bytes):
        if len(raw) != 20:
            raise ValueError(f"Address must be 20 bytes, got {len(raw)}")
        self._raw = raw

    @classmethod
    def from_hex(cls, s: str) -> "Address":
        return cls(bytes.fromhex(s.lower().removeprefix("0x")))

    def to_bytes(self) -> bytes:
        return self._raw

    def to_hex(self) -> str:
        return "0x" + self._raw.hex()

    def __eq__(self, other):
        return isinstance(other, Address) and self._raw == other._raw

    def __repr__(self):
        return f"Address({self.to_hex()})"
```

---

## 12. Runner 系统的地址迁移

> 本节专门描述 Runner 系统地址迁移的全部改动。Runner 既有链上部分 (system actors, storage keys)，也有链下部分 (Runner 节点本身的签名/注册)。

### 12.1 当前 Runner 地址架构

**核心问题**: Runner 使用 Ed25519 公钥 (32 字节) 同时作为 **身份标识 (identity)** 和 **地址**，两个职责耦合在一起。迁移后需要区分。

**Runner 关键类型** (`runner/src/types.rs`):

```rust
pub struct RunnerRegistration {
    pub address: PublicKey,    // Runner 地址 (32 字节 Ed25519) — 链上身份
    pub public_key: PublicKey, // Runner 签名验证公钥 (32 字节 Ed25519) — 与 address 相同
    // ...
}

pub struct JobSpec {
    pub submitter: PublicKey,  // 提交者地址 (32 字节 Ed25519)
    // ...
}

pub struct RunnerResult {
    pub runner: PublicKey,     // 提交结果的 Runner (32 字节 Ed25519)
    // ...
}
```

**Runner 存储键** (`runner/src/storage_keys.rs`):

```rust
// 键中嵌入 32 字节 PublicKey:
pub fn runner_key(address: &PublicKey) -> Vec<u8>      // "runner:" + 32B
pub fn runner_jobs_key(runner_address: &PublicKey)     // "runner_jobs:" + 32B
pub fn runner_result_key(job_id, runner: &PublicKey)   // "result:" + 32B + ":" + 32B
```

**Runner 注册序列化** (`runner/src/types.rs:392-393`):

```rust
state.serialize_field("address", &hex::encode(self.address.as_ref()))?;
state.serialize_field("public_key", &hex::encode(self.public_key.as_ref()))?;
// hex 编码: 64 字符 (32 字节)
```

**Runner 签名流程** (`chain/src/rpc.rs:2236-2300`):
- RPC 接受 `Path(address_hex)`: 解析为 `parse_public_key()` → Ed25519 `PublicKey`
- 签名消息 = `union_unique(NAMESPACE, &payload)` where NAMESPACE = `b"_COWBOY"`
- 验证: `runner_public.verify(NAMESPACE, &payload, &signature)` — Ed25519 验证

### 12.2 Runner 身份与地址的解耦

迁移后需要明确区分两个概念:

| 概念 | 迁移前 | 迁移后 |
|------|-------|-------|
| **Runner 链上地址** | Ed25519 PublicKey (32B) 作为地址 | 20 字节 Ethereum 地址 (secp256k1 派生) |
| **Runner 签名密钥** | Ed25519 PrivateKey | secp256k1 PrivateKey |
| **签名方案** | Ed25519 + `_COWBOY` namespace | ECDSA + EIP-155 |

**新设计**: Runner 地址 = `keccak256(secp256k1_pubkey)[12..32]`，与普通用户账户地址完全相同的派生方式，保持一致性。

### 12.3 Runner 类型系统改动

#### 12.3.1 RunnerRegistration

**文件**: `runner/src/types.rs`

```rust
// Before:
pub struct RunnerRegistration {
    pub address: PublicKey,    // Ed25519 32B
    pub public_key: PublicKey, // Ed25519 32B (与 address 相同)
    // ...
}

// After:
pub struct RunnerRegistration {
    pub address: Address,       // Ethereum 20B (secp256k1 派生)
    // public_key 字段可移除 —— 地址本身即是身份，验证时通过 ecrecover 恢复
    // 或保留为:
    // pub signing_key_hint: [u8; 33], // 压缩 secp256k1 公钥 (可选，用于快速验证)
    // ...
}
```

**Serialize/Deserialize 更新**:

```rust
// Before:
state.serialize_field("address", &hex::encode(self.address.as_ref()))?;  // 64 chars
// After:
state.serialize_field("address", &self.address.to_checksum_string())?;   // 0x + 40 chars
```

#### 12.3.2 JobSpec

**文件**: `runner/src/types.rs`

```rust
// Before:
pub struct JobSpec {
    pub submitter: PublicKey,  // Ed25519 32B
    // ...
}

// After:
pub struct JobSpec {
    pub submitter: Address,    // Ethereum 20B
    // ...
}
```

#### 12.3.3 RunnerResult

**文件**: `runner/src/types.rs`

```rust
// Before:
pub struct RunnerResult {
    pub runner: PublicKey,   // Ed25519 32B
    // ...
}

// After:
pub struct RunnerResult {
    pub runner: Address,     // Ethereum 20B
    // ...
}
```

#### 12.3.4 CallbackInfo

**文件**: `runner/src/types.rs` — `CallbackInfo` 中可能包含 actor 地址:

需要检查 `CallbackInfo` 的定义，将其中的地址字段 (`PublicKey` 类型) 改为 `Address`。

### 12.4 Runner 存储键改动

**文件**: `runner/src/storage_keys.rs`

所有使用 `PublicKey` 的存储键函数改为使用 `Address` (20 字节):

```rust
use cowboy_types::Address;  // 改为 Address 而非 PublicKey

pub mod runner_registry {
    // Before:
    pub fn runner_key(address: &PublicKey) -> Vec<u8> {
        let mut key = b"runner:".to_vec();
        key.extend_from_slice(address.as_ref());  // 32 bytes
        key  // total: 7 + 32 = 39 bytes
    }

    // After:
    pub fn runner_key(address: &Address) -> Vec<u8> {
        let mut key = b"runner:".to_vec();
        key.extend_from_slice(address.as_ref());  // 20 bytes
        key  // total: 7 + 20 = 27 bytes
    }

    // runner_jobs_key 同理
    pub fn runner_jobs_key(runner_address: &Address) -> Vec<u8> { ... }
}

pub mod result_verifier {
    // Before:
    pub fn runner_result_key(job_id: &[u8; 32], runner: &PublicKey) -> Vec<u8> {
        // "result:" + 32B + ":" + 32B = 73 bytes
    }

    // After:
    pub fn runner_result_key(job_id: &[u8; 32], runner: &Address) -> Vec<u8> {
        // "result:" + 32B + ":" + 20B = 61 bytes
    }
}
```

**数据影响**: 存储键格式变化意味着现有链上 Runner 注册数据不兼容，需要 Genesis 重置或数据迁移。

### 12.5 Runner 签名与 RPC 流程改动

**文件**: `chain/src/rpc.rs`

#### 12.5.1 地址解析

```rust
// Before:
let runner_public = parse_public_key(address_hex.trim_start_matches("0x"))?;
// address_hex: 64 chars hex (32 bytes)

// After:
let runner_address = Address::from_hex(address_hex.trim_start_matches("0x"))?;
// address_hex: 40 chars hex (20 bytes)
```

#### 12.5.2 get_runner_job_result_payload — 消息构造

Runner 需要签名的消息目前使用 Ed25519 payload 结构，迁移后改为 EIP-155 风格:

```rust
// Before:
let payload = Transaction::payload(&nonce, &instruction, ..., &[runner_public]);
let message_to_sign = union_unique(NAMESPACE, &payload);
// Runner 用 Ed25519 签名 message_to_sign

// After:
// 使用 keccak256 哈希作为签名消息
let tx_hash = keccak256(transaction_bytes);
let message_to_sign = eth_sign_prefix(tx_hash);  // \x19Ethereum Signed Message:\n32 + tx_hash
// Runner 用 secp256k1 ECDSA 签名
```

#### 12.5.3 submit_runner_job_result — 签名验证

```rust
// Before:
runner_public.verify(NAMESPACE, &payload, &signature)  // Ed25519 验证

// After:
let recovered = ecrecover(&message_hash, &eth_sig)?;
assert_eq!(recovered, runner_address)  // secp256k1 ecrecover 验证
```

#### 12.5.4 Heartbeat RPC

```rust
// Before:
Path(address_hex): Path<String>  // 64 chars
let runner_public = parse_public_key(address_hex)?;  // Ed25519 PublicKey

// After:
Path(address_hex): Path<String>  // 40 chars
let runner_address = Address::from_hex(address_hex)?;
```

### 12.6 chain/src/runner/ 内部逻辑改动

**文件**: `chain/src/runner/registry.rs`, `chain/src/runner/dispatcher.rs`, `chain/src/runner/verifier.rs`

#### registry.rs

- `handle_runner_register()` — 从 `RunnerRegistration` 中读取地址: `PublicKey` → `Address`
- `handle_runner_heartbeat()` — `runner: PublicKey` 参数 → `runner: Address`
- `handle_runner_deregister()` — 同上
- 活跃 Runner 列表序列化: 地址 hex 编码从 64 字符改为 40 字符

#### dispatcher.rs

- `handle_job_submit()` — `submitter` 字段: `PublicKey` → `Address`
- `select_runner_committee_simple()` — 返回 `Vec<PublicKey>` → `Vec<Address>`
- 存储 `job_runners` 列表时的地址 hex 编码格式变化

#### verifier.rs

- `handle_job_result_submit()` — `runner: PublicKey` → `runner: Address`
- `runner_result_key(job_id, runner)` — 参数类型 `PublicKey` → `Address`
- 共识阈值检查中的地址比较逻辑

### 12.7 SystemInstruction 中 Runner 相关字段

**文件**: `types/src/execution.rs`

```rust
// Before:
pub enum SystemInstruction {
    RunnerUpdateRateCard { runner: PublicKey, rate_card: Vec<u8> },
    RunnerHeartbeat { runner: PublicKey },
    RunnerDeregister { runner: PublicKey },
    // ...
}

// After:
pub enum SystemInstruction {
    RunnerUpdateRateCard { runner: Address, rate_card: Vec<u8> },
    RunnerHeartbeat { runner: Address },
    RunnerDeregister { runner: Address },
    // ...
}
```

`RunnerRegister` 中的 `registration` 字段是序列化的 `RunnerRegistration`，内部包含 `address` 和 `public_key`，序列化格式随类型变化而变化。

### 12.8 Runner 受影响文件总结

| 文件 | 修改内容 | 优先级 |
|------|---------|--------|
| `runner/src/types.rs` | `RunnerRegistration.address`, `JobSpec.submitter`, `RunnerResult.runner` 类型；序列化格式 | P1 |
| `runner/src/storage_keys.rs` | 所有接受 `&PublicKey` 的存储键函数改为 `&Address` | P1 |
| `runner/src/system_actors.rs` | 改为 `Address` 常量 (已在第 5 节覆盖) | P1 |
| `types/src/execution.rs` | `SystemInstruction` 中 Runner 相关字段 | P0 (已在 Phase 2 覆盖) |
| `chain/src/runner/registry.rs` | 地址类型适配，活跃列表格式 | P1 |
| `chain/src/runner/dispatcher.rs` | 地址类型适配，committee 选择 | P1 |
| `chain/src/runner/verifier.rs` | 地址类型适配，签名验证 | P1 |
| `chain/src/rpc.rs` | Runner RPC 端点地址解析、签名消息构造、ecrecover 验证 | P2 |

### 12.9 Runner 节点客户端的影响

Runner 节点本身 (链下软件) 也需要相应更新:

1. **密钥对类型**: 从 Ed25519 密钥对 → secp256k1 密钥对
2. **地址显示**: 从 64 字符 hex → `0x` + 40 字符 EIP-55
3. **心跳签名**: 使用 secp256k1 ECDSA 签名心跳消息
4. **结果提交签名**: 使用 secp256k1 ECDSA 签名结果 payload
5. **配置文件**: 私钥文件格式与用户钱包统一 (secp256k1, hex 编码)

---

> **下一步**: 确认方案选择后, 创建对应的 GitHub Issues 并按 Phase 分配实施任务。
