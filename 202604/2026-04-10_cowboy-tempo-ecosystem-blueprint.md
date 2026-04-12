# Cowboy Ecosystem Blueprint — Tempo 对标分析与实施规划

**Date:** 2026-04-09
**Status:** Draft
**Category:** Architecture / Ecosystem

---

## 目录

1. [Tempo 生态全景](#1-tempo-生态全景)
2. [Tempo 核心技术深度分析](#2-tempo-核心技术深度分析)
3. [Cowboy 现状盘点](#3-cowboy-现状盘点)
4. [差距分析](#4-差距分析)
5. [Cowboy 独特优势](#5-cowboy-独特优势)
6. [实施路线](#6-实施路线)
7. [各 Phase 详细设计](#7-各-phase-详细设计)
8. [依赖关系图](#8-依赖关系图)
9. [风险与决策点](#9-风险与决策点)

---

## 1. Tempo 生态全景

Tempo (https://github.com/tempoxyz) 是一条支付优化的 EVM 链，由 20+ 个仓库组成完整的开发者与用户生态。

### 1.1 仓库总览

| 仓库 | 星数 | 语言 | 定位 |
|------|------|------|------|
| **tempo** | 916 | Rust | 区块链节点（基于 Reth SDK） |
| **tempo-apps** | 193 | TypeScript | 6 个生产应用（浏览器、代付、代币注册等） |
| **tempo-foundry** | 74 | Rust | Foundry 分支（合约开发工具链） |
| **tidx** | 73 | Rust | 混合索引器（PostgreSQL + ClickHouse） |
| **tempo-std** | 64 | Solidity | 合约标准库（Precompile 接口 + 代币模板） |
| **tempo-go** | 64 | Go | Go SDK |
| **wallet** | 39 | Rust | CLI 钱包（Passkey 登录、402 支付） |
| **accounts** | — | TypeScript | TS SDK（核心：Passkey、wagmi、React hooks） |
| **pytempo** | 13 | Python | Python SDK |
| **mpp-specs** | — | Markdown | 机器支付协议规范（HTTP 402） |
| **mppx** | — | TypeScript | MPP TypeScript SDK（wevm 维护） |
| **pympp** | — | Python | MPP Python SDK |
| **mpp-rs** | — | Rust | MPP Rust SDK |
| **mpp-go** | — | Go | MPP Go SDK |
| **docs** | — | MDX | 文档站 (docs.tempo.xyz) |

### 1.2 架构拓扑

```
                        tempo (Rust 节点)
                       /       |        \
                tempo-std    tidx    tempo-foundry
               (Solidity)  (索引器)   (Foundry fork)
                    |
           [11 个 Precompile]
           [TIP-20 代币标准]
                    |
      +------------+------------+-----------+
      |            |            |           |
   accounts    tempo-go     pytempo      wallet
   (TS SDK)   (Go SDK)    (Py SDK)    (Rust CLI)
      |            |            |           |
      +------+-----+------+----+           |
             |                              |
       mppx (TS)  pympp  mpp-rs  mpp-go    |
             |       |      |       |       |
             +-------+------+------+--------+
                           |
                     mpp-specs (协议规范)
                           |
                    tempo-apps (6 个生产应用)
                    ├── Explorer (区块浏览器)
                    ├── Fee Payer (代付服务)
                    ├── Tokenlist (代币注册)
                    ├── Contract Verification (合约验证)
                    ├── Key Manager (WebAuthn 密钥管理)
                    └── OG (OpenGraph 图片生成)
```

---

## 2. Tempo 核心技术深度分析

### 2.1 节点架构

- **共识**: Simplex Consensus（基于 Commonware），亚秒级最终性
- **执行**: Reth SDK (Paradigm)，完整 EVM，目标 Osaka 硬分叉
- **编码**: Rust (edition 2024, rustc 1.93.0)
- **版本**: 1.5.2
- **Workspace**: 23+ 个 crate

**核心依赖:**

| 依赖 | 版本 | 用途 |
|------|------|------|
| Reth | rev 1911e57 | EVM 执行 + 节点框架 (40+ crate) |
| Alloy | v1.8.2 | 以太坊类型 / RPC / 传输层 |
| Commonware | v2026.3.0 | P2P / 广播 / 共识 / 密码学 |
| Revm | v36.0.0 | EVM 解释器 |
| Jsonrpsee | v0.26.0 | JSON-RPC 框架 |

**测试网 (Moderato):**

| 配置 | 值 |
|------|-----|
| Chain ID | 42431 |
| RPC (HTTP) | https://rpc.moderato.tempo.xyz |
| RPC (WS) | wss://rpc.moderato.tempo.xyz |
| Explorer | https://explore.tempo.xyz |
| 原生货币 | USD（非 ETH，费用以稳定币计价） |

### 2.2 交易格式 — Type 0x76

Tempo 最核心的创新是自定义交易类型，突破标准 EVM 交易的限制。

**线格式:** `0x76 || RLP([14 个字段])`

**签名后:** 追加第 15 个元素（65 字节 secp256k1 签名）

| 字段 | 类型 | 说明 |
|------|------|------|
| chainId | uint64 | 链 ID |
| maxPriorityFeePerGas | uint256 | EIP-1559 优先费 |
| maxFeePerGas | uint256 | EIP-1559 最大费用 |
| gasLimit | uint64 | Gas 上限 |
| **calls** | **TempoCall[]** | **原子批量调用：(to, value, data) 数组** |
| accessList | AccessListItem[] | EIP-2930 |
| **nonceKey** | **uint256** | **2D nonce — 并行执行通道** |
| nonce | uint64 | 通道内的序列号 |
| **validBefore** | **uint64** | **交易有效期截止** |
| **validAfter** | **uint64** | **交易有效期起始** |
| **feeToken** | **address** | **费用代币地址（任意稳定币）** |
| **feePayerSignature** | **bytes** | **Gas 代付者签名** |
| authorizationList | TempoAuthorization[] | EIP-7702 式授权 |
| keyAuthorization | bytes | 访问密钥授权 |

**关键设计:**
- `calls[]` 使一笔交易可以包含多个调用，原子执行（全成功或全回滚）
- `nonceKey` 实现 2D nonce：不同 key 的交易互不阻塞，可并行提交
- `feeToken` 允许用任意稳定币支付 Gas，而非必须持有原生代币
- `feePayerSignature` 在签名哈希中被排除（代付者独立签名），实现无需中继器的原生 Gas 代付
- 同时兼容 Legacy (type 0)、EIP-1559 (type 2)、EIP-7702 (type 4)

### 2.3 Precompile 系统

Tempo 在协议层内置 11 个预编译合约，提供系统级功能：

| Precompile | 地址前缀 | 功能 |
|------------|---------|------|
| **AccountKeychain** | 0xaAAA... | 访问密钥管理、WebAuthn、消费限额 |
| **TIP20Factory** | 0x20Fc... | 代币创建 / 部署 |
| **TIP403Registry** | 0x403c... | 合规/转账策略（白名单/黑名单/复合） |
| **StablecoinDEX** | 0xDEc0... | 链上稳定币 DEX（订单簿） |
| **FeeManager** | 0xfeEC... | 费用分配，用户/验证者代币偏好 |
| **Nonce** | 0x4e4F... | 2D nonce 查询 (key > 0) |
| **ValidatorConfig** | 0xCccC... | 验证者管理 |
| **ValidatorConfigV2** | 0xCcCC...01 | V2 验证者配置 |
| **AddressRegistry** | 0xfDC0... | 地址注册表 |
| **SignatureVerifier** | 0x5165... | 多方案签名验证 (secp256k1, P256, WebAuthn) |
| **TIP20RewardsRegistry** | 0x2100... | 代币奖励分发 |

### 2.4 代币标准 — TIP-20

ERC-20 的超集，针对支付场景增强：

**标准 ERC-20 基础:**
- balanceOf, transfer, approve, transferFrom
- permit (EIP-2612)

**支付增强:**
- `transferWithMemo(to, amount, memo)` — bytes32 备注（用于支付引用/PII）
- `systemTransferFrom` — 协议级转账
- `transferFeePreTx` / `transferFeePostTx` — Gas 费结算

**合规与治理:**
- 角色系统: ISSUER_ROLE, BURN_BLOCKED_ROLE, PAUSE_ROLE, UNPAUSE_ROLE
- 可配置供应上限 + mint/burn
- `burnBlocked(from, amount)` — 发行方可销毁冻结资金（监管要求）
- 每个代币关联一个 TIP-403 策略 ID（白名单/黑名单/复合）
- 全局暂停能力

**其他:**
- `quoteToken` 引用（用于 DEX 定价）
- 内置奖励分发系统（收益/质押）

### 2.5 账户抽象 — AccountKeychain

协议级智能账户系统（非 ERC-4337，无需 Bundler/Paymaster）：

**支持的签名方案:**
- secp256k1（传统 ECDSA）
- P256（NIST 曲线 — 支持 Passkey）
- WebAuthn（生物识别、硬件密钥）

**密钥管理 API:**
- `authorizeKey` — 添加有限制的访问密钥
- `revokeKey` — 撤销密钥
- `updateSpendingLimit` — 修改消费上限
- `setAllowedCalls` / `removeAllowedCalls` — 函数级调用控制

**密钥限制 (KeyRestrictions):**
- 过期时间
- 每代币消费限额（带周期重置）
- 调用范围（目标合约 + 函数选择器）
- 强制限额标记

**核心特性:**
- 有时效的 Session Key
- 无需部署智能合约钱包 — 内建于协议层
- 私钥永远不离开安全芯片（P256/WebAuthn）

### 2.6 机器支付协议 — MPP

与 Stripe 联合开发的跨链、支付方式无关的 HTTP 原生支付协议。

**标准流程:**

```
1. Client:  GET /resource
2. Server:  402 Payment Required
            WWW-Authenticate: Payment (challenge: 金额、方式等)
3. Client:  链上支付 (或 Stripe / Lightning / etc.)
4. Client:  GET /resource
            Authorization: Payment (支付证明)
5. Server:  验证支付 → 返回资源
```

**规范结构:**
- 核心: `draft-httpauth-payment-00.md` (HTTP 402 语义、Header、IANA 注册)
- 意图: `draft-payment-intent-charge-00.md` (charge, authorize, subscribe 模式)
- 方式: tempo, stripe, lightning, card, solana, stellar

**流式支付 (TempoStreamChannel):**
- 单向支付通道 + EIP-712 签名的 Voucher
- 流程: 开通道 → 充值 → 链下交换 voucher → 结算 → 关闭
- 支持: 追加充值、宽限期关闭、批量通道查询

**多语言 SDK:**

| 语言 | 仓库 | 特点 |
|------|------|------|
| TypeScript | mppx (wevm) | 客户端中间件、服务端 handler |
| Python | pympp | 服务端装饰器 `@server.pay(amount="0.50")`，异步客户端 |
| Rust | mpp-rs | Feature-flagged: client/server/tempo/stripe/axum/tower |
| Go | mpp-go | 早期阶段 |

### 2.7 SDK 生态

#### TypeScript SDK (`accounts`, v0.5.4)

```
包结构:
  ./          — 核心 (Provider, Store, Messenger)
  ./server    — 服务端适配
  ./cli       — CLI 工具
  ./react     — React hooks
  ./wagmi     — wagmi connector

适配器:
  tempoWallet  — 对话框/iframe 连接器
  webAuthn     — Passkey 适配器
  local        — 本地密钥
  dangerous_secp256k1 — 裸密钥（仅测试）

核心依赖:
  ox (v0.14.7) — viem 核心基础库
  mppx         — 机器支付
  webauthx     — WebAuthn 封装
  hono         — Web 框架
  zod          — Schema 验证
  zustand      — 状态管理

Peer 依赖:
  viem >= 2.43.3
  @wagmi/core >= 2
  react >= 18
```

#### Go SDK (`tempo-go`, v0.x)

```
基于 go-ethereum v1.17.0

包结构:
  transaction/ — 交易构建 (multi-call, sponsored, validity window)
  client/      — RPC 客户端
  signer/      — 签名器
  keychain/    — 密钥链管理

特性:
  - 批量调用构建
  - Gas 代付
  - 2D nonce
  - ERC20 helpers
```

#### Python SDK (`pytempo`)

```
基于 Web3.py

功能:
  TempoTransaction.create() — 完整 Tempo 交易构建器
  TIP20 helpers             — 代币操作
  StablecoinDEX helpers     — DEX 交互
  AccountKeychain helpers   — 密钥管理
  FeeAMM helpers            — 费用管理
  Nonce helpers             — 2D nonce 查询

支持: Gas 代付、并行 nonce、自选费用代币
```

#### Rust CLI (`wallet`)

```
命令:
  tempo wallet login        — Passkey 浏览器登录
  tempo wallet fund         — 水龙头
  tempo request <url>       — HTTP 请求 + 自动 402 支付
  session open/close        — 流式支付通道管理

依赖: alloy, clap, reqwest, rusqlite, minisign
```

### 2.8 基础设施

#### 索引器 (`tidx`)

```
架构: PostgreSQL (OLTP) + ClickHouse (OLAP)
特性: 实时同步 + 缺口回填

索引表: blocks, txs, logs, receipts, sync_state

HTTP API:
  /query    — SQL 查询 (支持 ABI 自动解码)
  /status   — 同步状态
  /health   — 健康检查
  /views    — 物化视图
  /metrics  — Prometheus 指标

查询路由: 点查询 → PostgreSQL, 聚合分析 → ClickHouse
配置: TOML
```

#### 生产应用 (`tempo-apps`)

```
技术栈: TypeScript, pnpm workspaces, Biome linter, Node 24

6 个应用:
  Explorer     — explore.tempo.xyz     — 区块浏览器 (主网/测试网/开发网)
  Fee Payer    — sponsor.testnet...    — 交易代付服务
  Tokenlist    — tokenlist.tempo.xyz   — 代币注册 API
  Contract Verification — contracts... — 合约验证服务
  Key Manager  — keys.tempo.xyz        — WebAuthn 密钥管理
  OG           — og.tempo.xyz          — OpenGraph 图片生成
```

#### 文档站 (`docs`)

```
站点: docs.tempo.xyz
框架: Vocs (自定义文档框架)
技术栈: React 19, Vite 8, Tailwind 4
集成: wagmi v3.4.2, viem v2.47.5, mppx, Stripe
测试: Playwright E2E
```

---

## 3. Cowboy 现状盘点

### 3.1 节点架构

| 组件 | 实现 |
|------|------|
| 共识 | Simplex Consensus (Commonware) |
| 执行 | PVM (Python VM) + 原生系统指令 |
| 语言 | Rust |
| 交易格式 | CBOR 编码, secp256k1 ECDSA |
| 地址 | 20 字节以太坊风格 (keccak256) |
| 状态存储 | QMDB (统一状态 DB) |

### 3.2 已有能力

**系统指令 (SystemInstruction):**
- CreateAccount, Transfer
- Runner 系列: Register, Heartbeat, Deregister, JobSubmit, JobResultSubmit, JobResultCommit, JobCancel
- Token 系列: TokenCreate, TokenMint, TokenBurn, TokenTransfer, TokenApprove, TokenTransferFrom, TokenFreeze, TokenUnfreeze, TokenSetHook, TokenTransferOwnership, TokenTransferBatch
- Entitlement 系列: Grant, Revoke, Delegate, CreateRole, AssignRole, RevokeRole
- FundActor, UpdateSettlementConfig

**Entitlement 系统（权限委托）:**

```rust
Scope:
  Global | Actor(Address) | Token([u8;32]) | Runner(Address)
  | RunnerPool(Vec<u8>) | Namespace(Vec<u8>)

Action:
  All | TokenTransfer | TokenMint | TokenBurn | TokenFreeze
  | TokenSetHook | TokenTransferOwnership | ActorDeploy
  | ActorSendMessage | ActorExecuteHandler(Vec<u8>)
  | RunnerRegister { min_stake_override } | RunnerSubmitJob | RunnerSubmitResult
  | RunnerJoinPool(Vec<u8>) | SystemTransfer | SystemCreateAccount
  | SystemUpgrade | UseOwnerBalance | Custom(Vec<u8>)

Constraints:
  valid_from / valid_until        — 时间窗口
  max_uses / used_count           — 使用次数
  max_amount_per_use              — 单次金额
  max_total_amount                — 总金额
  rate_limit (per_window, blocks) — 速率
  delegatable                     — 可否再委托
  delegation_depth_max            — 委托深度
  revocable                       — 可否撤销
```

**Runner 系统（链下计算）:**
- 注册、心跳、任务提交、结果提交、验证（多种模式）
- 争议与惩罚机制
- 结算分成 (89/10/1: runner/burn/treasury)

**CIP-20 代币:**
- 创建、铸造、销毁、转账、批准、冻结/解冻
- Hook 机制
- 所有权转移
- 批量转账

**RPC API:**
- /submit, /transaction, /account, /actor, /block, /height, /basefee
- /runner, /runners/active, /job (status/runners/results/verified)
- /proof (receipt/tx/account/actor/storage/multi)
- /token, /tokens
- /faucet (条件启用, CLI flag), /health, /metrics

**Client (Rust):**
- cowboy-client crate: RPC 客户端 + WebSocket + TLS

**Wallet (刚创建):**
- Passkey 方案 A (WebAuthn 保护加密的 secp256k1 密钥)
- 单 HTML 文件, server.js 代理

### 3.3 Crate 结构

```
node/
├── chain/       — 应用层 (engine, genesis, mempool, application)
├── client/      — Rust RPC 客户端
├── execution/   — 交易执行 (engine, PVM host, runner, entitlement, token, gas)
├── indexer/     — 简单索引器
├── rpc/         — HTTP/JSON API
├── storage/     — QMDB 存储层
├── types/       — 核心类型 (Address, Transaction, Signature, etc.)
├── token/       — CIP-20 代币类型
├── runner/      — Runner 系统类型
├── validator/   — 验证者入口
├── proof-verifier/ — 状态证明验证
├── pvm/         — Python VM
└── wallet/      — Passkey 钱包 (新)
```

---

## 4. 差距分析

### 4.1 协议层

| 能力 | Tempo | Cowboy | 状态 |
|------|-------|--------|------|
| 签名曲线 | secp256k1 + P256 + WebAuthn | 仅 secp256k1 | **需扩展曲线** |
| 多签名者 (一笔交易) | ❌ 单签名者 | ✅ `additional_signers` (AND 逻辑) | **Cowboy 已有** |
| 门限签名 (M-of-N) | 需合约 | Actor 层示例 (Safe 风格) | 应用层已覆盖 |
| 批量调用 | 原生 calls[] | 单条 instruction | **需新增** |
| 2D Nonce | nonceKey + nonce | 单一 nonce | **需新增** |
| 费用代币 | feeToken 字段 | 仅原生代币 | **需新增** |
| Gas 代付 | feePayerSignature | 无 | **需新增** |
| 有效期 | validBefore / validAfter | 无 | **需新增** |
| 账户抽象 | AccountKeychain precompile | Entitlement 系统 | **已有基础，需补 WebAuthn** |
| 代币标准 | TIP-20 (ERC-20+) | CIP-20 | **功能基本对齐** |
| 合规策略 | TIP-403 Registry | 无 | 需评估 |
| DEX | StablecoinDEX precompile | 无 | 需评估 |
| 流式支付 | TempoStreamChannel | 无 | Phase 4 |
| 链下计算 | 无 | Runner 系统 | **Cowboy 独有** |
| 权限委托 | AccountKeychain (密钥级) | Entitlement (多维度) | **Cowboy 更强** |

### 4.2 SDK 与工具

| 组件 | Tempo | Cowboy | 状态 |
|------|-------|--------|------|
| TypeScript SDK | accounts (完整) | 无 | **最大缺口** |
| Go SDK | tempo-go | 无 | 需新增 |
| Python SDK | pytempo | 无 | 需新增（PVM 用户核心需求） |
| Rust Client | alloy 扩展 | cowboy-client | **已有** |
| CLI 钱包 | wallet (Passkey + 402) | cowboy CLI (基础) | 需增强 |
| Foundry 工具 | tempo-foundry | N/A (非 EVM) | 不适用 |
| 合约标准库 | tempo-std (Solidity) | 无 (需 PVM 版) | 需新增 |

### 4.3 基础设施

| 组件 | Tempo | Cowboy | 状态 |
|------|-------|--------|------|
| 索引器 | tidx (PG + ClickHouse) | indexer (简单) | **需增强** |
| 区块浏览器 | explore.tempo.xyz | 无 | **需新建** |
| Gas 代付服务 | tempo-apps/fee-payer | 无 | 需新建 |
| 代币注册 | tempo-apps/tokenlist | 无 | 需新建 |
| 合约验证 | tempo-apps/contracts | N/A (非 EVM) | 不适用 |
| 密钥管理 | tempo-apps/key-manager | wallet (基础 Passkey) | 需增强 |
| 文档站 | docs.tempo.xyz (Vocs) | local_docs | **需增强** |
| 支付协议 | MPP (HTTP 402) | 无 | Phase 4 |

---

## 5. Cowboy 独特优势

Cowboy 有四项 Tempo 完全没有的能力：

### 5.1 PVM (Python VM)

- Actor 用 Python 编写，开发门槛极低
- 对 AI/ML 开发者友好（直接 import numpy/pandas 等）
- Tempo 开发者必须学 Solidity；Cowboy 开发者只需会 Python

### 5.2 Runner 系统（链下计算调度）

- 原生任务分发 + 验证 + 结算
- 支持多种验证模式: None, MajorityVote, StructuredMatch, Deterministic, EconomicBond, SemanticSimilarity
- 天然适配 AI Inference、Oracle、大规模计算场景
- Tempo 无此能力，链下计算需依赖外部服务

### 5.3 Entitlement 系统（多维权限模型）

比 Tempo 的 AccountKeychain 更强大：

| 维度 | Tempo AccountKeychain | Cowboy Entitlement |
|------|----------------------|-------------------|
| 粒度 | 密钥级限制 | 多维: Scope + Action + Constraints |
| 委托 | 无层级委托 | delegation_depth_max 多级链式委托 |
| 角色 | 无 | CreateRole / AssignRole |
| 作用域 | 合约 + 函数选择器 | Global / Actor / Token / Runner / Namespace |
| Gas 代付 | 通过 feePayerSignature | UseOwnerBalance (链上强制执行) |
| 速率限制 | 每代币消费限额 | 通用速率限制 (requests_per_window) |
| AI Agent 适配 | 弱（为人设计） | 强（原生支持程序化委托） |

### 5.4 Deferred Transactions（异步交易）

- Actor 可发起延迟交易（跨区块执行）
- 用于需要多步协调的复杂业务流程
- Tempo 无此能力

### 5.5 战略定位

```
Tempo = EVM + 支付优化 → 面向传统支付/合规场景
Cowboy = PVM + Runner + Entitlement → 面向 AI Agent + 链下计算场景

核心策略：
  补齐 Tempo 在支付基础设施上的能力（签名曲线、费用代币、批量调用、Gas 代付）
  保持并强化 Cowboy 在 AI Agent + 链下计算上的差异化
```

---

## 6. 实施路线

### 6.1 Phase 总览

```
Phase 0 — 协议层增强 (2-3 周)     ← 一切的基础
Phase 1 — SDK 生态 (2-3 周)       ← 开发者入口
Phase 2 — 基础设施 (3-4 周)       ← 生产就绪
Phase 3 — 开发者体验 (2 周)       ← 降低门槛
Phase 4 — 支付协议 (4+ 周)        ← 差异化
```

### 6.2 优先级矩阵

| 任务 | 优先级 | 依赖 |
|------|--------|------|
| P0.1 签名曲线扩展 (P256/WebAuthn) | 🔴 最高 | 无 |
| P0.2 交易格式扩展 | 🔴 最高 | P0.1 |
| P0.3 AccountKeychain 等价 | 🟡 中 | P0.1 |
| P1.1 TypeScript SDK | 🔴 最高 | P0.2 |
| P1.2 Python SDK | 🟡 中 | P0.2 |
| P1.3 Go SDK | 🟢 低 | P0.2 |
| P2.1 增强索引器 | 🔴 高 | 无 |
| P2.2 区块浏览器 | 🔴 高 | P2.1 |
| P2.3 Gas 代付服务 | 🟡 中 | P0.2 |
| P3.1 CLI 增强 | 🟡 中 | P0.1 |
| P3.2 cowboy-std | 🟡 中 | 无 |
| P3.3 文档站 | 🟡 中 | P1.1 |
| P4.1 MPP 规范适配 | 🟢 低 | P0.2 |
| P4.2 MPP SDK | 🟢 低 | P4.1 |

### 6.3 时间线

```
Step 1:   P0.1 (签名曲线扩展) + P2.1 (索引器，可并行)
Step 2:   P0.2 (交易格式) + P2.1 续
Step 3:   P1.1 (TS SDK) + P2.2 (浏览器)
Step 4:   P1.2 (Py SDK) + P0.3 (AccountKeychain) + P3.1 (CLI)
Step 5:   P2.3 (代付) + P3.2 (std) + P3.3 (文档)
Step 6:   Phase 4 (MPP)
```

---

## 7. 各 Phase 详细设计

### 7.1 Phase 0: 协议层增强

#### P0.1 — 签名曲线扩展 (P256 + WebAuthn)

**背景:** Cowboy 已原生支持"一笔交易多签名者"（`Transaction.additional_signers` + `sign_multi()`），主签名 AND 所有附加签名都必须通过验证才算有效。`payload_hash` 也把所有签名者地址纳入哈希以防替换。CreateAccount 等系统指令已依赖此能力。

**此任务不是新增多签名**，而是扩展**签名曲线**：让 `EthSignature` 之外的 P256 / WebAuthn 签名也能作为主签名或附加签名出现。

**目标:** 交易支持 secp256k1 + P256 (secp256r1) + WebAuthn 三种签名曲线，任意混用。

**修改文件:**

| 文件 | 变更 |
|------|------|
| `types/src/signature.rs` | 新增 `P256Signature`、`WebAuthnSignature`、`SignatureKind` enum；保留 `EthSignature` 为 secp256k1 变体 |
| `types/src/execution.rs` | `Transaction.signature` 和 `additional_signers` 元素类型改为 `SignatureKind`；`verify()` 按变体分支处理 |
| `types/src/address.rs` | 新增 `Address::from_p256_key()` |
| `execution/` | 无本质变更（`Transaction::verify()` 内部已统一处理多签名者） |

**签名类型设计:**

```rust
pub enum SignatureKind {
    /// 传统 secp256k1 ECDSA (65 bytes: r + s + v)
    Secp256k1(EthSignature),
    /// NIST P-256 / secp256r1 (用于 Passkey)
    P256 {
        r: [u8; 32],
        s: [u8; 32],
        public_key: [u8; 64], // 未压缩 P256 公钥 (去掉 0x04 前缀)
    },
    /// WebAuthn (P256 签名 + authenticator data)
    WebAuthn {
        r: [u8; 32],
        s: [u8; 32],
        public_key: [u8; 64],
        authenticator_data: Vec<u8>,
        client_data_json: Vec<u8>,
    },
}
```

**地址派生:**
- secp256k1: `keccak256(uncompressed[1..])[12..32]`（不变）
- P256: `keccak256(uncompressed_p256_key)[12..32]`（相同逻辑，不同曲线）
- WebAuthn: 与 P256 相同（WebAuthn 底层是 P256）

**向后兼容:**
- `SignatureKind::Secp256k1(EthSignature)` 分支复用现有 wire format（65 字节 r/s/v）
- 新增曲线通过 discriminant byte 区分，旧节点读到新变体会报 codec 错误（需配合 DB migration v1→v2 协调升级）
- `Transaction::sign_multi` 保持原语义；新增 `sign_multi_mixed` 接受 `Vec<Box<dyn Signer>>` 支持混合曲线

**新增依赖:**
- `p256` crate (RustCrypto P256 实现)
- `webauthn-rs-core` 或手写 WebAuthn clientDataJSON 解析（二选一）

#### P0.2 — 交易格式扩展

**目标:** 支持批量调用、2D nonce、费用代币、Gas 代付、有效期

**Transaction 结构变更:**

```rust
pub struct Transaction {
    // ── 现有字段 (保持不变) ──
    pub nonce: u64,
    pub instruction: Instruction,
    pub cycles_limit: u64,
    pub cells_limit: u64,
    pub max_fee_per_cycle: u64,
    pub max_fee_per_cell: u64,
    pub max_priority_fee_per_cycle: u64,
    pub max_priority_fee_per_cell: u64,
    pub from: Address,
    pub signature: SignatureKind,      // ← 改为 SignatureKind (P0.1)
    pub additional_signers: Vec<(Address, SignatureKind)>,
    pub origin_tx_hash: Option<Digest>,
    pub origin_remaining_cycles: Option<u64>,
    pub origin_remaining_cells: Option<u64>,
    pub metadata: Vec<u8>,             // 调用方附加元数据 (#141)

    // ── 新增字段 ──
    /// 批量调用：多条指令原子执行。为空时使用 instruction 字段。
    pub calls: Vec<Instruction>,

    /// 2D nonce key：不同 key 的交易互不阻塞。
    /// key=0 为默认通道（向后兼容现有单一 nonce）。
    pub nonce_key: u64,

    /// 费用代币：None 表示原生代币。
    pub fee_token: Option<Address>,

    /// Gas 代付者地址。
    pub fee_payer: Option<Address>,

    /// Gas 代付者签名（对交易 hash 的独立签名）。
    pub fee_payer_signature: Option<SignatureKind>,

    /// 交易有效期起始（区块高度）。
    pub valid_after: Option<u64>,

    /// 交易有效期截止（区块高度）。
    pub valid_before: Option<u64>,
}
```

**codec 向后兼容策略:**
- 新字段全部 `Option` 或有默认值
- `Read` impl 检测剩余字节：旧交易（无新字段）正常解码
- `calls` 为空时回退到 `instruction` 字段
- `nonce_key` 默认 0（等价于现有单通道 nonce）

**执行逻辑变更:**
- `execute_transaction`: 如果 `calls` 非空，依次执行所有指令，任一失败则全部回滚
- `nonce_key > 0` 时，从独立的 nonce 通道读取/递增
- `fee_token` 非 None 时，Gas 扣除改为从指定代币余额扣除
- `fee_payer` 非 None 时，Gas 从代付者账户扣除

**存储变更:**
- 2D nonce 需要新的 `StatePrefix`：`NonceChannel = 0x0E`
- Key: `[0x0E][20B address][8B nonce_key + 25B zero]`
- Value: `StateValue::SystemBytes(nonce.to_le_bytes())`
- 需要 DB migration v1→v2（使用已设计的迁移框架）

#### P0.3 — AccountKeychain 等价物

**评估:** Cowboy 的 Entitlement 系统已覆盖 Tempo AccountKeychain 的大部分能力：

| Tempo 能力 | Cowboy 对应 | 差距 |
|-----------|------------|------|
| Session key (时效) | Constraints.valid_from/valid_until | ✅ 已有 |
| 消费限额 | Constraints.max_amount_per_use/max_total_amount | ✅ 已有 |
| 速率限制 | Constraints.rate_limit | ✅ 已有 |
| 函数级控制 | Action::ActorExecuteHandler | ✅ 已有 |
| 层级委托 | EntitlementDelegate + delegation_depth_max | ✅ 已有 |
| Gas 代付 | Action::UseOwnerBalance | ✅ 已有 |
| WebAuthn 密钥注册 | — | ❌ 缺失 |
| 密钥撤销 | EntitlementRevoke | ✅ 已有 |

**需新增:**
- WebAuthn 密钥注册指令: `SystemInstruction::RegisterWebAuthnKey { public_key, credential_id }`
- 密钥-地址映射存储: 一个 P256 公钥可以控制一个 secp256k1 地址（通过 Entitlement 授权）

### 7.2 Phase 1: SDK 生态

#### P1.1 — TypeScript SDK

```
cowboy-sdk-ts/
├── packages/
│   ├── core/                — 核心库
│   │   ├── client.ts        — CowboyClient (RPC + WebSocket)
│   │   ├── transaction.ts   — TransactionBuilder
│   │   │                      支持 calls[], nonce_key, fee_token, fee_payer
│   │   ├── signer.ts        — 签名器接口
│   │   ├── address.ts       — 地址工具
│   │   ├── cip20.ts         — CIP-20 代币 helpers
│   │   ├── entitlement.ts   — Entitlement helpers
│   │   └── runner.ts        — Runner job helpers
│   │
│   ├── passkey/             — WebAuthn 适配器
│   │   ├── credential.ts    — Passkey 创建/登录
│   │   ├── signer.ts        — P256 签名器
│   │   └── store.ts         — 凭证存储
│   │
│   ├── react/               — React hooks
│   │   ├── useCowboy.ts     — Provider
│   │   ├── useAccount.ts    — 账户状态
│   │   ├── useBalance.ts    — 余额查询
│   │   ├── useSendTx.ts     — 发送交易
│   │   └── useTokens.ts     — CIP-20 操作
│   │
│   └── wagmi/               — wagmi connector (可选)
│       └── connector.ts
│
├── examples/
│   ├── basic-transfer/
│   ├── passkey-wallet/
│   ├── token-operations/
│   └── runner-job/
│
└── docs/

依赖:
  @noble/secp256k1, @noble/curves (P256), @noble/hashes
  cbor-x (CBOR 编解码)
  (不依赖 viem/ethers — Cowboy 不是 EVM 链)
```

#### P1.2 — Python SDK

```
pycowboy/
├── cowboy/
│   ├── client.py            — RPC 客户端 (requests/aiohttp)
│   ├── transaction.py       — 交易构建器
│   ├── signer.py            — secp256k1 / P256 签名
│   ├── address.py           — 地址工具
│   ├── cip20.py             — CIP-20 helpers
│   ├── entitlement.py       — Entitlement helpers
│   ├── runner.py            — Runner job helpers
│   └── types.py             — 类型定义
├── examples/
└── tests/

依赖:
  coincurve (secp256k1), cryptography (P256)
  cbor2 (CBOR), httpx (HTTP)
```

### 7.3 Phase 2: 基础设施

#### P2.1 — 增强索引器

```
架构:
  Cowboy Node → Indexer → PostgreSQL → HTTP API
                              ↘ ClickHouse (Phase 2.5, 可选)

PostgreSQL 表:
  blocks         (height, hash, timestamp, tx_count, state_root)
  transactions   (hash, block_height, tx_index, from, instruction_type, status)
  receipts       (tx_hash, status, cycles_used, cells_used, events)
  accounts       (address, nonce, balance, updated_at)
  actors         (address, code_hash, balance, updated_at)
  tokens         (token_id, name, symbol, supply, owner)
  token_balances (token_id, address, balance)
  events         (block_height, tx_index, event_type, data)
  runner_jobs    (job_id, status, runners, results)

HTTP API:
  GET  /blocks?limit=N&offset=M
  GET  /blocks/:height
  GET  /transactions/:hash
  GET  /accounts/:address
  GET  /accounts/:address/transactions
  GET  /actors/:address
  GET  /tokens
  GET  /tokens/:id
  GET  /tokens/:id/holders
  GET  /search?q=...
  GET  /status
  GET  /health
  GET  /metrics
```

#### P2.2 — 区块浏览器

```
技术栈: Next.js 15 + Tailwind 4 + 索引器 API

页面:
  /                          — 首页 (最新区块 + 交易)
  /blocks                    — 区块列表
  /block/:height             — 区块详情
  /tx/:hash                  — 交易详情 + 收据
  /account/:address          — 账户 (余额 + 交易历史)
  /actor/:address            — Actor (代码 + 存储 + 事件)
  /tokens                    — CIP-20 代币列表
  /token/:id                 — 代币详情 + 持有者
  /runners                   — Runner 列表
  /job/:id                   — Runner Job 详情

UI 风格: 复用现有 Cowboy demo 的暗色主题
```

#### P2.3 — Gas 代付服务

```
独立 HTTP 服务:

POST /sponsor
  Body: { transaction: <unsigned_tx> }
  
  流程:
  1. 验证交易白名单（发送者、目标、指令类型）
  2. 验证额度（每地址每日上限）
  3. 为 tx.fee_payer 填入服务地址
  4. 用服务密钥签名 fee_payer_signature
  5. 返回 { sponsored_transaction }

配置:
  - 白名单地址列表
  - 每地址每日额度
  - 支持的指令类型
  - 服务密钥 (secp256k1)

依赖: P0.2 (交易格式扩展)
```

### 7.4 Phase 3: 开发者体验

#### P3.1 — CLI 增强

```
新增命令:
  cowboy wallet login             — Passkey 浏览器登录 (打开本地 HTTP 服务)
  cowboy wallet fund              — 测试网水龙头
  cowboy wallet send <to> <amt>   — 转账
  cowboy wallet balance [addr]    — 余额查询
  cowboy token create             — 创建 CIP-20 代币
  cowboy token info <id>          — 代币信息
  cowboy runner submit <spec>     — 提交 Runner job
  cowboy runner status <job_id>   — 查询 job 状态
```

#### P3.2 — cowboy-std (PVM Actor 标准库)

```
cowboy-std/
├── cip20/
│   ├── token.py         — CIP-20 代币模板 Actor
│   └── helpers.py       — 代币操作 helpers
├── entitlement/
│   └── helpers.py       — 权限管理 helpers
├── runner/
│   └── helpers.py       — Runner job 提交 helpers
├── utils/
│   ├── storage.py       — 状态存储 helpers
│   └── events.py        — 事件发射 helpers
└── examples/
    ├── simple_token.py
    ├── nft_actor.py
    └── ai_agent.py
```

#### P3.3 — 文档站

```
技术栈: Nextra (或 Vocs) + MDX

结构:
  /                    — 首页
  /quickstart          — 5 分钟快速开始
  /concepts            — 概念 (Account, Actor, Token, Runner, Entitlement)
  /guides
    /create-token      — 创建代币
    /deploy-actor      — 部署 Actor
    /passkey-wallet    — Passkey 钱包
    /ai-agent          — AI Agent 授权
    /runner-job        — 链下计算
  /sdk
    /typescript        — TS SDK 参考
    /python            — Python SDK 参考
    /rust              — Rust Client 参考
  /api
    /rpc               — RPC API 参考
    /indexer           — 索引器 API 参考
  /specs
    /cip-20            — CIP-20 规范
    /entitlement       — Entitlement 规范
    /runner            — Runner 规范
```

### 7.5 Phase 4: 支付协议 (MPP)

```
Cowboy 版 MPP 设计:

与 Tempo MPP 的核心区别:
  - Tempo: 基于 EVM 交易 + 稳定币
  - Cowboy: 基于 Entitlement 授权 + Runner 系统

流程:
  1. AI Agent 请求 API:   GET /ai/inference
  2. Server 返回:         402 Payment Required
                          WWW-Authenticate: Payment method="cowboy",
                            amount="100", token="<CIP20_ID>",
                            recipient="<server_addr>"
  3. Agent 用 Entitlement 授权支付:
     - 如果 Agent 有预授权的 Entitlement → 直接链上转账
     - 如果没有 → 请求人类授权
  4. Agent 附带支付证明:   GET /ai/inference
                          Authorization: Payment tx_hash="0x..."
  5. Server 验证支付 → 返回推理结果

Cowboy 的优势:
  - Entitlement 的 rate_limit 天然防止 Agent 超额消费
  - UseOwnerBalance 让 Agent 无需自己持有代币
  - Runner 系统可直接承载推理任务（无需外部 API）
```

---

## 8. 依赖关系图

```
P0.1 签名曲线扩展 ─────┬──→ P0.2 交易格式 ──→ P1.1 TS SDK
                      │                    ├─→ P1.2 Py SDK
                      │                    ├─→ P2.3 Gas 代付
                      │                    └─→ P4.x MPP
                      └──→ P0.3 Keychain
                      └──→ P3.1 CLI 增强

P2.1 索引器 (独立) ──────→ P2.2 浏览器

P3.2 cowboy-std (独立)

P3.3 文档站 ──────────────→ 依赖 P1.1 + P1.2 完成
```

可并行的工作流:
- **工作流 A**: P0.1 → P0.2 → P1.1/P1.2 → P2.3 → P4.x（协议 + SDK + 支付）
- **工作流 B**: P2.1 → P2.2（索引器 + 浏览器，完全独立）
- **工作流 C**: P3.2（cowboy-std，完全独立）

---

## 9. 风险与决策点

### 9.1 协议变更的共识影响

**风险:** P0.2 的交易格式扩展是硬分叉级别的变更。

**缓解:**
- 所有新字段设为 Option，codec 向后兼容
- 分阶段激活：先部署代码，通过治理提案在指定区块高度启用
- 先在测试网验证 2+ 周

### 9.2 QMDB 无 iteration 的限制

**风险:** 如果迁移需要遍历所有数据（如改变 Account 编码），QMDB 不支持。

**缓解:**
- 优先使用 codec 向后兼容策略（读取时惰性升级）
- 不兼容变更通过共识层重放处理
- 已设计好 DB migration 框架（version + 迁移链）

### 9.3 P256 签名验证性能

**风险:** P256 验证比 secp256k1 慢（约 2-3x），可能影响交易吞吐。

**缓解:**
- P256 验证可并行化
- 多数交易仍使用 secp256k1（P256 仅用于 Passkey 场景）
- 可选：预编译 P256 验证库（如 RustCrypto 的 `p256` crate 已有优化）

### 9.4 SDK 生态维护负担

**风险:** 4 种语言的 SDK 维护成本高。

**缓解:**
- 优先 TypeScript + Python（覆盖 90% 用例）
- Go SDK 推迟到有社区需求时
- 自动化测试：每个 SDK 对同一节点运行相同的集成测试套件

### 9.5 是否跟随 Tempo 的 EVM 路线

**决策点:** Cowboy 要不要也支持 EVM？

**建议: 不。**
- Cowboy 的差异化在于 PVM + Runner，不应变成"另一条 EVM 链"
- 支持 EVM 意味着需要维护两套执行环境（巨大工程量）
- Tempo 的 EVM 特性（Foundry、Solidity 合约、EIP 兼容）不适用于 Cowboy
- 专注于让 Python Actor 生态做到最好

### 9.6 MPP 是否需要与 Stripe 合作

**决策点:** Cowboy 的 MPP 实现是否需要支持 Stripe 等传统支付。

**建议: Phase 4 先只支持 Cowboy 原生支付，后续按需扩展。**
- Tempo 与 Stripe 的合作是其商业优势，Cowboy 不需要复制
- Cowboy 的 MPP 应聚焦 AI Agent 场景：Agent 用 Entitlement 自动支付
- 传统支付可作为 Phase 5 按需补充
