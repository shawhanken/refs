# Runner 系统详细设计与实现方案

**文档版本**: 1.0  
**创建日期**: 2026-01-27  
**状态**: 设计阶段  


---

## 📋 执行摘要

Runner 系统是 Cowboy 链的核心创新，提供**可验证的链下计算市场**。本文档提供 Runner 系统的完整架构设计、组件划分、接口定义和分阶段实现路径，确保系统具备**可扩展性**、**安全性**和**长期可维护性**。

### 核心目标

1. **可验证性**: 支持多种信任模型（N-of-M、TEE、ZK V2）
2. **开放性**: 自由市场定价，Runner 自主报价
3. **可靠性**: 健康检查、故障转移、争议解决
4. **扩展性**: 支持多种任务类型（LLM、HTTP、自定义）
5. **安全性**: 密钥管理、访问控制、防攻击机制

---

## 🏗️ 第一部分：系统架构

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      Cowboy Chain (On-Chain)                     │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Actor A    │  │   Actor B    │  │   Actor C    │         │
│  │  (PVM)       │  │  (PVM)       │  │  (PVM)       │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                 │                 │                  │
│         └─────────────────┼─────────────────┘                  │
│                           │                                      │
│                  ┌────────▼────────┐                            │
│                  │ Runner Registry │                            │
│                  │  (System Actor) │                            │
│                  │  0xRUNNER_REG   │                            │
│                  └────────┬────────┘                            │
│                           │                                      │
│                  ┌────────▼────────┐                            │
│                  │  Job Dispatcher │                            │
│                  │  (System Actor) │                            │
│                  │  0xJOB_DISPATCH │                            │
│                  └────────┬────────┘                            │
│                           │                                      │
│                  ┌────────▼────────┐                            │
│                  │ Result Verifier │                            │
│                  │  (System Actor) │                            │
│                  │  0xRESULT_VERIF │                            │
│                  └────────┬────────┘                            │
│                           │                                      │
│                  ┌────────▼────────┐                            │
│                  │ Secrets Manager │                            │
│                  │  (System Actor) │                            │
│                  │  0xSECRETS_MGR  │                            │
│                  └─────────────────┘                            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ Message Passing
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    Runner Network (Off-Chain)                    │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Runner 1    │  │  Runner 2    │  │  Runner 3    │         │
│  │  (LLM/HTTP)  │  │  (LLM/HTTP)  │  │  (TEE)       │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                 │                 │                  │
│         └─────────────────┼─────────────────┘                  │
│                           │                                      │
│                  ┌────────▼────────┐                            │
│                  │  Consensus Layer │                            │
│                  │  (N-of-M/TEE)   │                            │
│                  └────────┬────────┘                            │
│                           │                                      │
│                  ┌────────▼────────┐                            │
│                  │  Result Aggreg. │                            │
│                  └─────────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 核心组件

#### 1.2.1 链上组件（System Actors）

| 组件 | 地址 | 职责 | 状态 |
|------|------|------|------|
| **Runner Registry** | `0xRUNNER_REG` | Runner 注册、费率卡管理、健康检查 | 🔴 待实现 |
| **Job Dispatcher** | `0xJOB_DISPATCH` | 任务分发、Runner 选择、任务队列 | 🔴 待实现 |
| **Result Verifier** | `0xRESULT_VERIF` | 结果验证、共识聚合、争议处理 | 🔴 待实现 |
| **Secrets Manager** | `0xSECRETS_MGR` | 密钥存储、访问控制、TEE 集成 | 🔴 待实现 |
| **TEE Verifier** | `0xTEE_VERIF` | TEE 证明验证、密钥管理 | 🔴 待实现 |

#### 1.2.2 链下组件（Runner Executor）

| 组件 | 位置 | 职责 | 状态 |
|------|------|------|------|
| **Runner Node** | `crates/runner/` | 任务执行、结果提交、健康上报 | 🔴 待实现 |
| **LLM Executor** | `crates/runner/llm/` | LLM 推理、模型管理 | 🔴 待实现 |
| **HTTP Executor** | `crates/runner/http/` | HTTP 请求、数据提取 | 🔴 待实现 |
| **TEE Runtime** | `crates/runner/tee/` | TEE 环境、证明生成 | 🔴 待实现 |
| **Consensus Client** | `crates/runner/consensus/` | N-of-M 投票、结果聚合 | 🔴 待实现 |

### 1.3 系统独立性说明

**重要**: Runner 系统是架构上**完全独立**于 Node 和 PVM 的新系统。理解这种独立性对于正确设计和实现 Runner 系统至关重要。

#### 1.3.1 架构关系图

```
┌─────────────────────────────────────────────────────────┐
│                    Cowboy Chain Node                     │
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Consensus Layer (Simplex BFT)                │   │
│  └──────────────────┬────────────────────────────┘   │
│                     │                                   │
│  ┌──────────────────▼────────────────────────────┐   │
│  │  Transaction Execution Layer                  │   │
│  │  ┌─────────────────────────────────────────┐ │   │
│  │  │  PVM (Python Virtual Machine)           │ │   │
│  │  │  - 执行 Actor 的 Python 代码            │ │   │
│  │  │  - Checkpoint/Resume                    │ │   │
│  │  │  - HostApi 接口                         │ │   │
│  │  └─────────────────────────────────────────┘ │   │
│  └──────────────────┬────────────────────────────┘   │
│                     │                                   │
│  ┌──────────────────▼────────────────────────────┐   │
│  │  System Actors (链上)                        │   │
│  │  - Runner Registry                           │   │
│  │  - Job Dispatcher                            │   │
│  │  - Result Verifier                           │   │
│  └──────────────────┬────────────────────────────┘   │
└──────────────────────┼───────────────────────────────────┘
                       │
                       │ 消息传递 (Message Passing)
                       │
┌──────────────────────▼───────────────────────────────────┐
│              Runner Network (链下独立系统)                │
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Runner 1    │  │  Runner 2    │  │  Runner 3    │ │
│  │  (独立进程)   │  │  (独立进程)   │  │  (独立进程)   │ │
│  │              │  │              │  │              │ │
│  │  - LLM API   │  │  - HTTP      │  │  - TEE       │ │
│  │  - 本地模型   │  │  - 数据提取   │  │  - 证明生成   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                           │
│  完全独立运行，不依赖 Node 或 PVM                          │
└───────────────────────────────────────────────────────────┘
```

#### 1.3.2 系统定位对比

| 系统 | 位置 | 职责 | 依赖关系 | 特点 |
|------|------|------|---------|------|
| **PVM** | 链上，运行在 Node 内部 | 执行 Actor 的 Python 代码 | 依赖 Node 提供 HostApi、状态存储 | 确定性执行、单块原子性 |
| **Node** | 链上 | 共识、交易执行、状态管理 | 包含 PVM 作为执行引擎 | 参与共识、维护状态 |
| **Runner** | 链下，完全独立 | 执行 LLM、HTTP 等链下任务 | 通过消息与链上通信 | 独立进程、不参与共识、不执行 PVM 代码 |

#### 1.3.3 独立性体现

**1. 部署独立性**
- ✅ Runner 可以独立部署，不依赖 Node
- ✅ 可以运行在不同的机器、不同的网络
- ✅ 可以运行在不同的云服务商、不同的数据中心

**2. 代码独立性**
- ✅ Runner 有自己的代码库（`crates/runner/`）
- ✅ 不包含 PVM 代码
- ✅ 不包含 Node 代码
- ✅ 可以独立开发和维护

**3. 运行时独立性**
- ✅ Runner 是独立的进程/服务
- ✅ 不执行 Python 代码（除非是本地模型推理）
- ✅ 不参与链上共识
- ✅ 不维护链上状态

**4. 网络独立性**
- ✅ Runner 网络是独立的 P2P 网络
- ✅ 与链节点网络分离
- ✅ 可以有自己的网络拓扑和路由策略

#### 1.3.4 通信方式

Runner 系统与链上系统通过**消息传递**进行通信：

```python
# Actor (在 PVM 中运行)
@runner.continuation
async def analyze(self, msg):
    # 1. 发送任务到链上 System Actor
    result = await runner.llm("Analyze market trends...")
    #     ↓
    # 2. 链上 Job Dispatcher 分发任务
    #     ↓
    # 3. Runner 网络执行（链下，完全独立）
    #     ↓
    # 4. 结果返回链上 Result Verifier
    #     ↓
    # 5. 验证后回调 Actor
    return result
```

**通信流程**:
1. **任务提交**: Actor → Job Dispatcher (链上 System Actor)
2. **任务分发**: Job Dispatcher → Runner Network (链下)
3. **任务执行**: Runner Network (独立执行，不依赖链)
4. **结果提交**: Runner Network → Result Verifier (链上 System Actor)
5. **结果回调**: Result Verifier → Actor (通过消息)

#### 1.3.5 设计优势

这种独立架构设计带来以下优势：

**1. 解耦**
- ✅ Runner 故障不影响链的正常运行
- ✅ 链的升级不影响 Runner 网络
- ✅ 可以独立扩展和优化

**2. 扩展性**
- ✅ Runner 网络可以独立扩展（增加更多 Runner）
- ✅ 不增加链节点的负担
- ✅ 可以支持不同类型的 Runner（LLM、HTTP、自定义）

**3. 安全性**
- ✅ 链下执行不影响共识安全
- ✅ Runner 攻击不会影响链的完整性
- ✅ 通过验证机制保证结果正确性

**4. 灵活性**
- ✅ Runner 可以使用任意技术栈（不限于 Rust）
- ✅ 可以集成第三方服务（OpenAI、Anthropic 等）
- ✅ 可以支持硬件加速（GPU、TPU 等）

#### 1.3.6 实现注意事项

在设计 Runner 系统时，必须牢记其独立性：

1. **不要假设 Runner 可以访问 PVM**
   - Runner 不执行 Python 代码
   - Runner 不访问 Actor 状态
   - Runner 只接收任务参数，返回结果

2. **不要假设 Runner 可以访问 Node 内部**
   - Runner 不参与共识
   - Runner 不维护链状态
   - Runner 只通过标准接口与链通信

3. **设计时考虑网络延迟和故障**
   - Runner 可能在任意时刻离线
   - 网络可能分区
   - 需要超时和重试机制

4. **确保接口的稳定性和版本兼容性**
   - 链上接口变更不应破坏 Runner
   - Runner 升级不应影响链
   - 需要版本协商机制

---

## 🔧 第二部分：详细设计

### 2.1 Runner Registry（Runner 注册表）

#### 2.1.1 数据结构

```rust
// crates/runner-registry/src/lib.rs

/// Runner 注册信息
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunnerRegistration {
    /// Runner 地址（20 字节）
    pub address: Address,
    
    /// Runner 公钥（用于签名验证）
    pub public_key: PublicKey,
    
    /// 质押金额（CBY）
    pub stake: U256,
    
    /// 费率卡
    pub rate_card: RateCard,
    
    /// 能力声明
    pub capabilities: RunnerCapabilities,
    
    /// 健康状态
    pub health: HealthStatus,
    
    /// 注册时间（区块高度）
    pub registered_at: BlockHeight,
    
    /// 最后心跳时间
    pub last_heartbeat: BlockHeight,
    
    /// 声誉分数（0-100）
    pub reputation: u8,
    
    /// 活跃任务数
    pub active_jobs: u32,
}

/// 费率卡
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RateCard {
    /// LLM 输入 token 价格（CBY wei per token）
    pub llm_input_token: U256,
    
    /// LLM 输出 token 价格
    pub llm_output_token: U256,
    
    /// HTTP 请求基础价格
    pub http_request_base: U256,
    
    /// 计算时间价格（per second）
    pub compute_second: U256,
    
    /// 内存价格（per MB）
    pub memory_mb: U256,
    
    /// 支持的模型列表（模型哈希）
    pub supported_models: Vec<ModelHash>,
    
    /// 最小任务价值
    pub min_job_value: U256,
    
    /// 最大任务价值
    pub max_job_value: U256,
    
    /// 费率卡更新冷却期（区块数）
    pub cooldown_blocks: BlockHeight,
    
    /// 上次更新时间
    pub last_updated: BlockHeight,
}

/// Runner 能力
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunnerCapabilities {
    /// 支持的任务类型
    pub job_types: Vec<JobType>,
    
    /// TEE 支持
    pub tee_support: Option<TeeType>,
    
    /// 区域限制
    pub regions: Vec<String>,
    
    /// 域名访问权限
    pub http_domains: Vec<String>,
    
    /// 最大并发任务数
    pub max_concurrent_jobs: u32,
}

/// 健康状态
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HealthStatus {
    /// 健康（最近心跳正常）
    Healthy,
    
    /// 不健康（心跳超时）
    Unhealthy,
    
    /// 已暂停（主动暂停）
    Paused,
    
    /// 已注销
    Deregistered,
}
```

#### 2.1.2 核心接口

```rust
// crates/runner-registry/src/lib.rs

pub trait RunnerRegistry {
    /// 注册 Runner
    fn register_runner(
        &mut self,
        registration: RunnerRegistration,
        signature: Signature,
    ) -> Result<(), RegistryError>;
    
    /// 更新费率卡
    fn update_rate_card(
        &mut self,
        runner: Address,
        new_rate_card: RateCard,
    ) -> Result<(), RegistryError>;
    
    /// 心跳
    fn heartbeat(&mut self, runner: Address) -> Result<(), RegistryError>;
    
    /// 查询活跃 Runner 列表
    fn get_active_runners(
        &self,
        filter: RunnerFilter,
    ) -> Vec<RunnerRegistration>;
    
    /// 根据 VRF 选择 Runner 委员会
    fn select_committee(
        &self,
        job_spec: &JobSpec,
        vrf_seed: [u8; 32],
    ) -> Result<Vec<Address>, RegistryError>;
    
    /// 更新声誉
    fn update_reputation(
        &mut self,
        runner: Address,
        delta: i8,
    ) -> Result<(), RegistryError>;
}
```

#### 2.1.3 健康检查机制

```rust
// 健康检查规则
const HEARTBEAT_TIMEOUT_BLOCKS: BlockHeight = 100; // ~100 秒

fn check_health(&self, runner: &RunnerRegistration, current_block: BlockHeight) -> HealthStatus {
    let blocks_since_heartbeat = current_block.saturating_sub(runner.last_heartbeat);
    
    if blocks_since_heartbeat > HEARTBEAT_TIMEOUT_BLOCKS {
        HealthStatus::Unhealthy
    } else {
        HealthStatus::Healthy
    }
}
```

### 2.2 Job Dispatcher（任务分发器）

#### 2.2.1 任务规范

```rust
// crates/job-dispatcher/src/lib.rs

/// 任务规范
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JobSpec {
    /// 任务 ID（由 Actor 生成）
    pub job_id: JobId,
    
    /// 任务类型
    pub job_type: JobType,
    
    /// 任务参数（类型相关）
    pub params: JobParams,
    
    /// 资源边界
    pub bounds: ResourceBounds,
    
    /// 验证配置
    pub verification: VerificationConfig,
    
    /// 最大价格（CBY wei）
    pub max_price: U256,
    
    /// 优先级小费
    pub tip: U256,
    
    /// 超时（区块数）
    pub timeout_blocks: BlockHeight,
    
    /// 回调信息
    pub callback: CallbackInfo,
    
    /// 提交者（Actor 地址）
    pub submitter: Address,
    
    /// 提交区块高度
    pub submitted_at: BlockHeight,
}

/// 任务类型
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum JobType {
    /// LLM 推理
    Llm {
        model_id: ModelHash,
        prompt: String,
        system_prompt: Option<String>,
        temperature: Option<f64>,
        max_tokens: u32,
        response_model: Option<JsonSchema>,
    },
    
    /// HTTP 请求
    Http {
        url: String,
        method: HttpMethod,
        headers: HashMap<String, String>,
        body: Option<Vec<u8>>,
        extraction: Option<ExtractionConfig>,
        freshness: Option<FreshnessConfig>,
    },
    
    /// 自定义任务（V2）
    Custom {
        executor_hash: Hash,
        params: Vec<u8>,
    },
}

/// 资源边界
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceBounds {
    /// 最大输入 tokens
    pub max_input_tokens: u32,
    
    /// 最大输出 tokens
    pub max_output_tokens: u32,
    
    /// 最大执行时间（秒）
    pub max_wall_time_seconds: u64,
    
    /// 最大内存（MB）
    pub max_memory_mb: u32,
    
    /// 最大重试次数
    pub max_retries: u32,
}

/// 验证配置
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationConfig {
    /// 验证模式
    pub mode: VerificationMode,
    
    /// Runner 数量
    pub runners: u32,
    
    /// 阈值（N-of-M 中的 N）
    pub threshold: u32,
    
    /// 检查器列表
    pub checks: Vec<VerifierCheck>,
    
    /// TEE 要求
    pub tee_required: bool,
    
    /// 争议窗口（区块数）
    pub dispute_window_blocks: BlockHeight,
}
```

#### 2.2.2 Runner 选择算法

```rust
// crates/job-dispatcher/src/selection.rs

/// Runner 选择器
pub struct RunnerSelector {
    registry: Arc<dyn RunnerRegistry>,
    vrf: VrfProvider,
}

impl RunnerSelector {
    /// 选择 Runner 委员会
    pub fn select_committee(
        &self,
        job_spec: &JobSpec,
        current_block: BlockHeight,
    ) -> Result<Vec<Address>, SelectionError> {
        // 1. 过滤符合条件的 Runner
        let candidates = self.filter_candidates(job_spec)?;
        
        if candidates.len() < job_spec.verification.runners as usize {
            return Err(SelectionError::InsufficientRunners);
        }
        
        // 2. 使用 VRF 确定性选择
        let vrf_seed = self.generate_vrf_seed(job_spec, current_block);
        let selected = self.vrf_select(
            &candidates,
            job_spec.verification.runners as usize,
            &vrf_seed,
        )?;
        
        Ok(selected)
    }
    
    /// 过滤候选 Runner
    fn filter_candidates(
        &self,
        job_spec: &JobSpec,
    ) -> Result<Vec<RunnerRegistration>, SelectionError> {
        let all_runners = self.registry.get_active_runners(RunnerFilter::default());
        
        let candidates: Vec<_> = all_runners
            .into_iter()
            .filter(|runner| {
                // 健康检查
                runner.health == HealthStatus::Healthy
                    // 能力匹配
                    && self.matches_capabilities(runner, job_spec)
                    // 价格匹配
                    && self.matches_price(runner, job_spec)
                    // 声誉检查
                    && runner.reputation >= MIN_REPUTATION
                    // 并发限制
                    && runner.active_jobs < runner.capabilities.max_concurrent_jobs
            })
            .collect();
        
        Ok(candidates)
    }
    
    /// 能力匹配
    fn matches_capabilities(
        &runner: &RunnerRegistration,
        job_spec: &JobSpec,
    ) -> bool {
        // 检查任务类型支持
        if !runner.capabilities.job_types.contains(&job_spec.job_type) {
            return false;
        }
        
        // 检查 TEE 要求
        if job_spec.verification.tee_required {
            if runner.capabilities.tee_support.is_none() {
                return false;
            }
        }
        
        // 检查模型支持（LLM 任务）
        if let JobType::Llm { model_id, .. } = &job_spec.job_type {
            if !runner.rate_card.supported_models.contains(model_id) {
                return false;
            }
        }
        
        // 检查域名访问（HTTP 任务）
        if let JobType::Http { url, .. } = &job_spec.job_type {
            if let Some(domain) = extract_domain(url) {
                if !runner.capabilities.http_domains.contains(&domain)
                    && !runner.capabilities.http_domains.contains(&"*".to_string())
                {
                    return false;
                }
            }
        }
        
        true
    }
    
    /// 价格匹配
    fn matches_price(
        &runner: &RunnerRegistration,
        job_spec: &JobSpec,
    ) -> bool {
        let expected_price = self.estimate_price(runner, job_spec);
        expected_price <= job_spec.max_price
            && job_spec.max_price >= runner.rate_card.min_job_value
            && job_spec.max_price <= runner.rate_card.max_job_value
    }
}
```

### 2.3 Result Verifier（结果验证器）

#### 2.3.1 验证模式实现

```rust
// crates/result-verifier/src/verification.rs

/// 验证器
pub struct ResultVerifier {
    registry: Arc<dyn RunnerRegistry>,
    tee_verifier: Arc<dyn TeeVerifier>,
}

impl ResultVerifier {
    /// 验证结果
    pub fn verify_results(
        &self,
        job_spec: &JobSpec,
        results: Vec<RunnerResult>,
    ) -> Result<VerifiedResult, VerificationError> {
        match job_spec.verification.mode {
            VerificationMode::None => {
                self.verify_none(results)
            }
            VerificationMode::EconomicBond => {
                self.verify_economic_bond(job_spec, results)
            }
            VerificationMode::MajorityVote => {
                self.verify_majority_vote(job_spec, results)
            }
            VerificationMode::StructuredMatch => {
                self.verify_structured_match(job_spec, results)
            }
            VerificationMode::Deterministic => {
                self.verify_deterministic(job_spec, results)
            }
            VerificationMode::SemanticSimilarity => {
                self.verify_semantic_similarity(job_spec, results)
            }
        }
    }
    
    /// N-of-M 多数投票验证
    fn verify_majority_vote(
        &self,
        job_spec: &JobSpec,
        results: Vec<RunnerResult>,
    ) -> Result<VerifiedResult, VerificationError> {
        if results.len() < job_spec.verification.runners as usize {
            return Err(VerificationError::InsufficientResults);
        }
        
        // 提取投票字段
        let vote_field = job_spec
            .verification
            .checks
            .iter()
            .find_map(|check| {
                if let VerifierCheck::MajorityVote { field } = check {
                    Some(field)
                } else {
                    None
                }
            })
            .ok_or(VerificationError::InvalidConfig)?;
        
        // 统计投票
        let mut vote_counts: HashMap<String, u32> = HashMap::new();
        for result in &results {
            if let Some(value) = extract_field(&result.data, vote_field) {
                let key = serde_json::to_string(&value).unwrap();
                *vote_counts.entry(key).or_insert(0) += 1;
            }
        }
        
        // 找到多数
        let (winning_value, count) = vote_counts
            .into_iter()
            .max_by_key(|(_, count)| *count)
            .ok_or(VerificationError::NoConsensus)?;
        
        if count < job_spec.verification.threshold {
            return Err(VerificationError::ThresholdNotMet);
        }
        
        // 选择第一个匹配的结果作为最终结果
        let final_result = results
            .into_iter()
            .find(|r| {
                extract_field(&r.data, vote_field)
                    .and_then(|v| serde_json::to_string(&v).ok())
                    .map(|s| s == winning_value)
                    .unwrap_or(false)
            })
            .ok_or(VerificationError::NoConsensus)?;
        
        Ok(VerifiedResult {
            data: final_result.data,
            consensus_count: count,
            total_runners: job_spec.verification.runners,
        })
    }
    
    /// 结构化匹配验证
    fn verify_structured_match(
        &self,
        job_spec: &JobSpec,
        results: Vec<RunnerResult>,
    ) -> Result<VerifiedResult, VerificationError> {
        // 对每个检查器运行验证
        for check in &job_spec.verification.checks {
            match check {
                VerifierCheck::JsonSchemaValid { schema } => {
                    // 验证所有结果都符合 schema
                    for result in &results {
                        if !validate_json_schema(&result.data, schema) {
                            return Err(VerificationError::SchemaMismatch);
                        }
                    }
                }
                VerifierCheck::StructuredMatch { fields } => {
                    // 检查指定字段是否匹配
                    if !self.check_fields_match(&results, fields) {
                        return Err(VerificationError::FieldMismatch);
                    }
                }
                VerifierCheck::NumericTolerance { field, tolerance } => {
                    // 检查数值是否在容差范围内
                    if !self.check_numeric_tolerance(&results, field, *tolerance) {
                        return Err(VerificationError::ToleranceExceeded);
                    }
                }
                // ... 其他检查器
                _ => {}
            }
        }
        
        // 如果所有检查通过，选择第一个有效结果
        Ok(VerifiedResult {
            data: results[0].data.clone(),
            consensus_count: results.len() as u32,
            total_runners: job_spec.verification.runners,
        })
    }
    
    /// 确定性验证（精确匹配 + TEE）
    fn verify_deterministic(
        &self,
        job_spec: &JobSpec,
        results: Vec<RunnerResult>,
    ) -> Result<VerifiedResult, VerificationError> {
        // 1. 检查所有结果是否字节级相同
        let first_result = &results[0];
        for result in &results[1..] {
            if result.data != first_result.data {
                return Err(VerificationError::NonDeterministic);
            }
        }
        
        // 2. 验证 TEE 证明（如果要求）
        if job_spec.verification.tee_required {
            for result in &results {
                if let Some(attestation) = &result.tee_attestation {
                    self.tee_verifier.verify(attestation)?;
                } else {
                    return Err(VerificationError::MissingTeeAttestation);
                }
            }
        }
        
        Ok(VerifiedResult {
            data: first_result.data.clone(),
            consensus_count: results.len() as u32,
            total_runners: job_spec.verification.runners,
        })
    }
}
```

### 2.4 Runner Executor（Runner 执行器）

#### 2.4.1 架构设计

```rust
// crates/runner/src/lib.rs

/// Runner 节点
pub struct RunnerNode {
    /// Runner 配置
    config: RunnerConfig,
    
    /// 链连接
    chain_client: Arc<dyn ChainClient>,
    
    /// 任务执行器
    executors: HashMap<JobType, Box<dyn JobExecutor>>,
    
    /// 任务队列
    job_queue: Arc<Mutex<VecDeque<Job>>>,
    
    /// 健康检查器
    health_checker: HealthChecker,
    
    /// 声誉管理器
    reputation_manager: ReputationManager,
}

impl RunnerNode {
    /// 启动 Runner 节点
    pub async fn start(&mut self) -> Result<(), RunnerError> {
        // 1. 注册到链上
        self.register_on_chain().await?;
        
        // 2. 启动任务监听
        self.start_job_listener().await?;
        
        // 3. 启动健康检查
        self.start_health_checker().await?;
        
        // 4. 启动任务执行器
        self.start_executors().await?;
        
        Ok(())
    }
    
    /// 监听链上任务
    async fn start_job_listener(&mut self) -> Result<(), RunnerError> {
        loop {
            // 查询是否有分配给本 Runner 的任务
            let jobs = self.chain_client.get_assigned_jobs(self.config.address).await?;
            
            for job in jobs {
                self.job_queue.lock().unwrap().push_back(job);
            }
            
            tokio::time::sleep(Duration::from_secs(1)).await;
        }
    }
    
    /// 执行任务
    async fn execute_job(&self, job: Job) -> Result<JobResult, RunnerError> {
        let executor = self.executors
            .get(&job.spec.job_type)
            .ok_or(RunnerError::UnsupportedJobType)?;
        
        // 执行任务
        let result = executor.execute(&job.spec).await?;
        
        // 提交结果到链上
        self.chain_client.submit_result(job.job_id, result).await?;
        
        Ok(result)
    }
}
```

#### 2.4.2 LLM 执行器

```rust
// crates/runner/src/llm/executor.rs

pub struct LlmExecutor {
    /// 模型管理器
    model_manager: ModelManager,
    
    /// API 客户端（OpenAI、Anthropic 等）
    api_clients: HashMap<String, Box<dyn LlmApiClient>>,
    
    /// 本地模型运行时（可选）
    local_runtime: Option<LocalModelRuntime>,
}

impl JobExecutor for LlmExecutor {
    async fn execute(&self, spec: &JobSpec) -> Result<JobResult, ExecutorError> {
        let JobType::Llm {
            model_id,
            prompt,
            system_prompt,
            temperature,
            max_tokens,
            response_model,
        } = &spec.job_type else {
            return Err(ExecutorError::InvalidJobType);
        };
        
        // 1. 选择执行方式（API 或本地）
        let execution_mode = self.select_execution_mode(model_id)?;
        
        // 2. 执行推理
        let response = match execution_mode {
            ExecutionMode::Api { client } => {
                client
                    .chat_completion(ChatRequest {
                        model: model_id.to_string(),
                        messages: vec![
                            if let Some(sys) = system_prompt {
                                Message::system(sys.clone())
                            } else {
                                Message::system("You are a helpful assistant.".to_string())
                            },
                            Message::user(prompt.clone()),
                        ],
                        temperature: *temperature,
                        max_tokens: *max_tokens,
                    })
                    .await?
            }
            ExecutionMode::Local { runtime } => {
                runtime.infer(InferenceRequest {
                    model_id: *model_id,
                    prompt: prompt.clone(),
                    max_tokens: *max_tokens,
                })
                .await?
            }
        };
        
        // 3. 验证响应格式（如果指定了 response_model）
        if let Some(schema) = response_model {
            validate_against_schema(&response.content, schema)?;
        }
        
        // 4. 计算资源使用
        let usage = ResourceUsage {
            input_tokens: response.usage.prompt_tokens,
            output_tokens: response.usage.completion_tokens,
            wall_time_seconds: response.duration.as_secs(),
            memory_mb: response.memory_usage_mb,
        };
        
        // 5. 生成 TEE 证明（如果要求）
        let tee_attestation = if spec.verification.tee_required {
            Some(self.generate_tee_attestation(&response, &usage).await?)
        } else {
            None
        };
        
        Ok(JobResult {
            data: serde_json::to_value(&response.content)?,
            usage,
            tee_attestation,
            timestamp: SystemTime::now(),
        })
    }
}
```

#### 2.4.3 HTTP 执行器

```rust
// crates/runner/src/http/executor.rs

pub struct HttpExecutor {
    /// HTTP 客户端
    http_client: reqwest::Client,
    
    /// 提取器（CSS、XPath、JSONPath）
    extractors: HashMap<String, Box<dyn DataExtractor>>,
}

impl JobExecutor for HttpExecutor {
    async fn execute(&self, spec: &JobSpec) -> Result<JobResult, ExecutorError> {
        let JobType::Http {
            url,
            method,
            headers,
            body,
            extraction,
            freshness,
        } = &spec.job_type else {
            return Err(ExecutorError::InvalidJobType);
        };
        
        // 1. 执行 HTTP 请求
        let mut request = self.http_client.request(*method, url);
        
        for (key, value) in headers {
            request = request.header(key, value);
        }
        
        if let Some(body) = body {
            request = request.body(body.clone());
        }
        
        let response = request.send().await?;
        let status = response.status();
        let raw_body = response.bytes().await?;
        
        // 2. 检查新鲜度
        if let Some(freshness) = freshness {
            self.check_freshness(&response, freshness)?;
        }
        
        // 3. 数据提取（如果指定）
        let extracted_data = if let Some(extraction) = extraction {
            self.extract_data(&raw_body, extraction)?
        } else {
            serde_json::json!({ "raw": base64::encode(&raw_body) })
        };
        
        // 4. 生成源证明
        let attestation = SourceAttestation {
            fetch_timestamp: SystemTime::now(),
            url: url.clone(),
            http_status: status.as_u16(),
            response_hash: keccak256(&raw_body),
            tls_cert_fingerprint: self.extract_tls_fingerprint(&response)?,
            response_headers: response.headers().clone(),
        };
        
        Ok(JobResult {
            data: extracted_data,
            usage: ResourceUsage {
                input_tokens: 0,
                output_tokens: raw_body.len() as u32,
                wall_time_seconds: response.elapsed().as_secs(),
                memory_mb: 0,
            },
            tee_attestation: None,
            source_attestation: Some(attestation),
            timestamp: SystemTime::now(),
        })
    }
}
```

---

## 🛣️ 第三部分：实现路径

### 3.1 阶段划分

#### 阶段 1：基础框架（4-5 周）

**目标**: 建立 Runner 系统的基础架构和核心组件

**任务**:
1. **Runner Registry 实现**（1 周）
   - 注册/注销接口
   - 费率卡管理
   - 健康检查机制
   - 基础查询接口

2. **Job Dispatcher 实现**（1.5 周）
   - 任务提交接口
   - Runner 选择算法（VRF）
   - 任务队列管理
   - 超时处理

3. **基础 Runner Executor**（1.5 周）
   - Runner 节点框架
   - 链连接（Chain Client）
   - 任务监听和执行循环
   - 结果提交

4. **HTTP Executor**（1 周）
   - HTTP 请求执行
   - 基础数据提取
   - 源证明生成

**验收标准**:
- ✅ Runner 可以注册到链上
- ✅ Actor 可以提交 HTTP 任务
- ✅ Runner 可以执行 HTTP 任务并返回结果
- ✅ 基础验证（none 模式）工作

#### 阶段 2：LLM 集成（2-3 周）

**目标**: 实现 LLM 任务执行和基础验证

**任务**:
1. **LLM Executor**（1.5 周）
   - OpenAI API 集成
   - Anthropic API 集成
   - 本地模型支持（可选）
   - 资源计量

2. **基础验证模式**（1 周）
   - `none` 模式
   - `economic_bond` 模式
   - `majority_vote` 模式

3. **Result Verifier**（0.5 周）
   - 结果聚合
   - 投票统计
   - 争议窗口

**验收标准**:
- ✅ Actor 可以调用 `runner.llm()`
- ✅ Runner 可以执行 LLM 任务
- ✅ N-of-M 投票验证工作
- ✅ 结果正确路由回 Actor

#### 阶段 3：高级验证（3-4 周）

**目标**: 实现完整的验证模式和争议解决

**任务**:
1. **结构化匹配验证**（1 周）
   - JSON Schema 验证
   - 字段匹配
   - 数值容差检查
   - 自定义验证器

2. **语义相似度验证**（1 周）
   - 嵌入向量生成
   - 相似度计算
   - 阈值判断

3. **争议解决机制**（1 周）
   - 争议提交
   - 证据收集
   - 仲裁流程
   - 惩罚机制

4. **TEE 支持（基础）**（1 周）
   - TEE 证明生成
   - 证明验证
   - TEE Verifier 系统 Actor

**验收标准**:
- ✅ 所有验证模式可用
- ✅ 争议可以提交和解决
- ✅ TEE 证明可以验证
- ✅ 声誉系统工作

#### 阶段 4：优化和扩展（2-3 周）

**目标**: 性能优化、安全加固、功能扩展

**任务**:
1. **性能优化**（1 周）
   - 任务队列优化
   - 批量处理
   - 缓存机制

2. **安全加固**（1 周）
   - 密钥管理
   - Secrets Manager 实现
   - 访问控制

3. **监控和可观测性**（0.5 周）
   - 指标收集
   - 日志系统
   - 告警机制

4. **文档和测试**（0.5 周）
   - API 文档
   - 集成测试
   - 压力测试

**验收标准**:
- ✅ 系统性能满足要求
- ✅ 安全审计通过
- ✅ 完整文档和测试覆盖

### 3.2 技术栈选择

#### 链上组件（Rust）

```toml
# crates/runner-registry/Cargo.toml
[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
sha2 = "0.10"
ed25519-dalek = "2.0"
bls12_381 = "0.7"  # VRF
```

#### 链下组件（Rust + Tokio）

```toml
# crates/runner/Cargo.toml
[dependencies]
tokio = { version = "1.35", features = ["full"] }
reqwest = { version = "0.11", features = ["json", "rustls-tls"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
async-openai = "0.20"  # OpenAI API
anthropic = "0.20"     # Anthropic API
onnxruntime = "0.19"   # 本地模型（可选）
```

### 3.3 关键设计决策

#### 决策 1：异步任务框架

**选择**: 完全异步、解耦的任务生命周期

**理由**:
- 避免阻塞链上执行
- 支持长时间运行的任务
- 允许故障恢复和重试

**实现**:
- 任务提交立即返回
- Runner 异步执行
- 结果通过回调返回

#### 决策 2：自由市场定价

**选择**: Runner 自主定价，Actor 设置上限

**理由**:
- 价格发现更高效
- 适应不同资源成本
- 避免协议层面的复杂计算

**实现**:
- Runner 发布费率卡
- Actor 设置 `max_price`
- 实际支付 = `min(usage × rates, max_price)`

#### 决策 3：分层验证模型

**选择**: 多种验证模式，从简单到复杂

**理由**:
- 不同场景需要不同信任级别
- 成本与安全性平衡
- 渐进式采用

**实现**:
- `none`: 无验证（开发/测试）
- `economic_bond`: 经济担保
- `majority_vote`: 多数投票
- `structured_match`: 结构化匹配
- `deterministic`: 确定性 + TEE
- `semantic_similarity`: 语义相似度

---

## 🔒 第四部分：安全考虑

### 4.1 攻击向量和缓解措施

| 攻击向量 | 风险 | 缓解措施 |
|---------|------|---------|
| **Runner 恶意结果** | 🔴 高 | N-of-M 共识、争议机制、声誉系统 |
| **价格操纵** | ⚠️ 中 | 费率卡冷却期、价格带限制 |
| **Sybil 攻击** | ⚠️ 中 | 质押要求、声誉衰减 |
| **资源耗尽** | ⚠️ 中 | 资源边界、超时机制 |
| **密钥泄露** | 🔴 高 | Secrets Manager、TEE 隔离 |
| **TEE 证明伪造** | 🔴 高 | 密钥注册表、证明验证 |

### 4.2 安全机制

#### 4.2.1 质押和惩罚

```rust
// 最小质押要求
const MIN_RUNNER_STAKE: U256 = U256::from(50_000_000_000_000_000_000u128); // 50,000 CBY

// 惩罚规则
pub enum SlashingReason {
    /// 提交错误结果
    InvalidResult { severity: u8 },
    
    /// 超时未提交
    Timeout,
    
    /// 资源使用虚报
    Overcharge { multiplier: f64 },
    
    /// 争议失败
    DisputeLost,
}

fn calculate_slash(reason: SlashingReason, stake: U256) -> U256 {
    match reason {
        SlashingReason::InvalidResult { severity } => {
            stake * U256::from(severity) / U256::from(100)
        }
        SlashingReason::Timeout => stake * U256::from(5) / U256::from(100),
        SlashingReason::Overcharge { multiplier } => {
            stake * U256::from((multiplier * 100.0) as u64) / U256::from(100)
        }
        SlashingReason::DisputeLost => stake * U256::from(30) / U256::from(100),
    }
}
```

#### 4.2.2 争议解决

```rust
// 争议窗口
const DISPUTE_WINDOW_BLOCKS: BlockHeight = 900; // ~15 分钟

// 争议类型
pub enum DisputeType {
    /// Actor 挑战 Runner（价格虚报）
    Overcharge {
        job_id: JobId,
        evidence: OverchargeEvidence,
    },
    
    /// Runner 挑战 Actor（不公平故障分配）
    UnfairFault {
        job_id: JobId,
        evidence: FaultEvidence,
    },
    
    /// 第三方挑战（串通）
    Collusion {
        job_id: JobId,
        evidence: CollusionEvidence,
    },
}

// 仲裁流程
pub struct Arbitration {
    /// 争议 ID
    dispute_id: DisputeId,
    
    /// 挑战者
    challenger: Address,
    
    /// 被挑战者
    challenged: Address,
    
    /// 争议类型
    dispute_type: DisputeType,
    
    /// 证据
    evidence: Vec<Evidence>,
    
    /// 仲裁者（VRF 选择）
    arbitrators: Vec<Address>,
    
    /// 投票结果
    votes: HashMap<Address, bool>,
    
    /// 结果
    resolution: Option<ArbitrationResolution>,
}
```

---

## 📊 第五部分：扩展性设计

### 5.1 水平扩展

#### 5.1.1 Runner 网络扩展

- **无上限**: Runner 数量无硬性限制
- **自动发现**: 通过 Registry 自动发现新 Runner
- **负载均衡**: VRF 选择确保负载分布

#### 5.1.2 任务类型扩展

```rust
// 插件化任务类型
pub trait JobExecutor: Send + Sync {
    async fn execute(&self, spec: &JobSpec) -> Result<JobResult, ExecutorError>;
    
    fn estimate_cost(&self, spec: &JobSpec) -> U256;
    
    fn validate_bounds(&self, spec: &JobSpec) -> Result<(), ValidationError>;
}

// 注册自定义执行器
pub struct ExecutorRegistry {
    executors: HashMap<JobType, Box<dyn JobExecutor>>,
}

impl ExecutorRegistry {
    pub fn register_executor(
        &mut self,
        job_type: JobType,
        executor: Box<dyn JobExecutor>,
    ) {
        self.executors.insert(job_type, executor);
    }
}
```

### 5.2 垂直扩展

#### 5.2.1 性能优化

- **批量处理**: 批量提交结果
- **缓存**: 缓存常用数据
- **异步 I/O**: 全异步架构

#### 5.2.2 资源管理

- **连接池**: HTTP 客户端连接池
- **内存管理**: 限制并发任务数
- **CPU 调度**: 任务优先级队列

---

## 🧪 第六部分：测试策略

### 6.1 单元测试

```rust
#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_runner_selection() {
        // 测试 Runner 选择算法
    }
    
    #[tokio::test]
    async fn test_majority_vote_verification() {
        // 测试多数投票验证
    }
    
    #[tokio::test]
    async fn test_price_calculation() {
        // 测试价格计算
    }
}
```

### 6.2 集成测试

```rust
#[tokio::test]
async fn test_end_to_end_llm_job() {
    // 1. Actor 提交 LLM 任务
    // 2. Runner 选择
    // 3. Runner 执行
    // 4. 结果验证
    // 5. 回调 Actor
}
```

### 6.3 压力测试

- **并发任务**: 1000+ 并发任务
- **Runner 数量**: 100+ Runner
- **网络延迟**: 模拟网络延迟
- **故障注入**: 模拟 Runner 故障

---

## 📚 第七部分：文档和示例

### 7.1 API 文档

- Runner Registry API
- Job Dispatcher API
- Result Verifier API
- Runner Executor API

### 7.2 使用示例

```python
# Actor 端示例
from cowboy_sdk import runner, Verify

@runner.continuation
async def analyze_market(self, msg):
    ctx = capture()
    
    ctx.analysis = await runner.llm(
        prompt="Analyze BTC market trends...",
        verification=Verify.builder()
            .mode("structured_match")
            .runners(5)
            .threshold(3)
            .check(Verify.json_schema_valid(AnalysisSchema))
            .check(Verify.numeric_tolerance("score", 0.05))
            .build(),
        timeout_blocks=100,
    )
    
    self.execute_trade(ctx.analysis)
```

---

## 🎯 第八部分：里程碑和验收

### 8.1 关键里程碑

| 里程碑 | 时间 | 交付物 | 验收标准 |
|--------|------|--------|---------|
| **M1: 基础框架** | 5 周 | Registry + Dispatcher + HTTP Executor | HTTP 任务端到端可用 |
| **M2: LLM 集成** | 8 周 | LLM Executor + 基础验证 | LLM 任务可用，N-of-M 工作 |
| **M3: 完整验证** | 12 周 | 所有验证模式 + 争议解决 | 所有验证模式可用 |
| **M4: 生产就绪** | 15 周 | 优化 + 安全 + 文档 | 性能达标，安全审计通过 |

### 8.2 验收标准

#### 功能验收
- ✅ 所有核心功能实现
- ✅ 所有验证模式工作
- ✅ 争议解决机制可用
- ✅ TEE 支持可用

#### 性能验收
- ✅ 任务延迟 < 5 秒（HTTP）
- ✅ 任务延迟 < 30 秒（LLM，API）
- ✅ 支持 1000+ 并发任务
- ✅ Runner 选择 < 1 秒

#### 安全验收
- ✅ 安全审计通过
- ✅ 争议机制测试通过
- ✅ 攻击向量测试通过
- ✅ TEE 证明验证正确

---

## 📝 总结

Runner 系统是 Cowboy 链的核心创新，需要**系统化、模块化、可扩展**的设计。本文档提供了：

1. **完整架构**: 链上/链下组件清晰划分
2. **详细设计**: 每个组件的接口和实现
3. **实现路径**: 分阶段、可验收的实现计划
4. **安全考虑**: 攻击向量和缓解措施
5. **扩展性**: 支持未来功能扩展

**关键原则**:
- ✅ **立足长远**: 设计考虑未来扩展
- ✅ **不短视**: 不为了快速实现而牺牲质量
- ✅ **模块化**: 组件独立，易于测试和维护
- ✅ **安全性**: 多层安全机制
- ✅ **可观测性**: 完整的监控和日志

**预计总工作量**: **15 周（约 4 个月）**

---

**文档维护**: 本文档应随实现进展持续更新，记录设计决策和变更。
