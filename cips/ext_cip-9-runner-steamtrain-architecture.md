# Runner 与 Steamtrain 物理架构关系

**参考文档：** CIP-9（Runner 可挂载存储）、CIP-10（容器运行时）

---

## 一、核心结论：库而非进程

**`steamtrain-client` 是一个 Rust 库（crate），静态链接进 Runner 二进制文件，不是独立进程，不是 sidecar，不是守护进程。**

```
Runner 进程（单一 OS 进程）
┌─────────────────────────────────────────────────────┐
│  runner-core          （作业调度、CIP-2 生命周期）    │
│  steamtrain-client    （存储库，编译时链入）          │
│    ├── fuse.rs        （FUSE 挂载实现）              │
│    ├── quic.rs        （与远程存储节点的 QUIC 连接） │
│    └── crypto.rs      （CapToken 验证、AES-256-GCM）│
└─────────────────────────────────────────────────────┘
```

Runner 直接调用 `steamtrain-client` 的函数，走进程内函数调用，没有 IPC、没有网络跳转。

---

## 二、完整物理拓扑

```
┌───────────────────────────────────────────────────────────────┐
│  Runner 节点（一台物理机 / VM）                                 │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Runner 进程                                             │  │
│  │                                                        │  │
│  │  runner-core ──调用──► steamtrain-client               │  │
│  │                           │                           │  │
│  │                           ├── CapToken 链下验证         │  │
│  │                           ├── AES-256-GCM 加密/解密    │  │
│  │                           └── FUSE 驱动（用户态）       │  │
│  │                                    │                   │  │
│  └────────────────────────────────────│───────────────────┘  │
│                                       │ FUSE 内核接口          │
│                              /mnt/steamtrain/               │
│                              /mnt/secrets/ ...              │
│                              （宿主 OS 挂载点）              │
│                                                               │
│  [容器作业时]                                                   │
│  ┌─────────────────────────────────────────┐                 │
│  │ 容器 mount namespace                    │                 │
│  │   /mnt/steamtrain ◄── bind-mount ───────┤── 同上挂载点    │
│  │   /overlay-rootfs （容器文件系统）       │                 │
│  └─────────────────────────────────────────┘                 │
└───────────────────────────────────────────────────────────────┘
                         │
                         │  QUIC（加密传输，远程）
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  Steamtrain 存储集群                                          │
│                                                              │
│  Node-1  Node-2  Node-3  ...  Node-N                        │
│  ┌─────┐ ┌─────┐ ┌─────┐     ┌─────┐                       │
│  │分片1│ │分片2│ │分片3│     │奇偶 │  Reed-Solomon 纠删码   │
│  │密文 │ │密文 │ │密文 │     │校验 │  K 数据 + M 奇偶分片   │
│  └─────┘ └─────┘ └─────┘     └─────┘                       │
│                                                              │
│  存储节点只见密文，永远无法访问明文                             │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、数据流详解

### 写入路径

```
Runner 进程
    │
    │  1. Runner 业务代码写入 /mnt/steamtrain/file
    │
    ▼
FUSE 内核接口（拦截 write 系统调用）
    │
    ▼
steamtrain-client / fuse.rs（用户态 FUSE handler）
    │
    │  2. AES-256-GCM 加密（crypto.rs）
    │     key 由 steamtrain-client 管理，Runner 进程内持有
    │
    ▼
steamtrain-client / quic.rs
    │
    │  3. QUIC 传输加密分片
    │     Reed-Solomon 编码：K 个数据分片 + M 个奇偶分片
    │
    ▼
Steamtrain 存储节点（仅收到密文分片）
```

### 读取路径（逆序）

```
Steamtrain 存储节点
    │  取回 ≥ K 个分片（Reed-Solomon 解码）
    ▼
steamtrain-client / quic.rs
    │
    ▼
steamtrain-client / crypto.rs（AES-256-GCM 解密）
    │  解密在 Runner 进程内完成
    ▼
FUSE 内核接口（返回明文给 read 系统调用）
    │
    ▼
Runner 业务代码 / 容器进程 读到明文
```

---

## 四、`steamtrain-client` 仓库结构

```
steamtrain-client/              ← 独立 Rust crate（CIP-9 定义）
  Cargo.toml                    ← 仅 runner 工作空间依赖，node 不依赖
  src/
    lib.rs          ← 重新导出 trait 和类型
    traits.rs       ← 四个核心 trait（见下）
    types.rs        ← CapToken、VolumeMount、VolumeMode、StorageError
    fuse.rs         ← FUSE 挂载实现（用户态文件系统）
    quic.rs         ← 与 Steamtrain 存储节点的 QUIC 传输
    crypto.rs       ← CapToken secp256k1 验证 + AES-256-GCM 加解密
```

**四个核心 Trait：**

| Trait | 实现方 | 职责 |
|-------|--------|------|
| `VolumeProvider` | `steamtrain-client` | `mount_volume` / `unmount_volume` / `verify_cap_token` |
| `AuthProvider` | Runner | 验证 CapToken 合法性，返回 `VolumeClaims` |
| `AuthoritativeStore` | 节点（node crate） | 将 `manifest_root` 提交上链 |
| `ManifestRegistry` | 节点（node crate） | 查询卷元数据、清理过期 token |

> `AuthProvider` 和 `AuthoritativeStore` 由外部注入——这是依赖倒置设计，让 `steamtrain-client` 不依赖具体的链节点实现。

---

## 五、非容器作业 vs 容器作业的挂载差异

### 非容器作业（Llm / Http / Custom）

```
Runner 进程
    └── mount_volume() → /mnt/steamtrain（宿主 OS 路径）
    └── 业务代码直接读写 /mnt/steamtrain
    └── unmount_volume() → 返回 manifest_root
```

Runner 进程与挂载点在同一 OS namespace，直接访问。

### 容器作业（Container，CIP-10）

```
Runner 进程
    │
    ├── 1. mount_volume() → /mnt/steamtrain（宿主 OS 路径）
    │        FUSE 挂载点已在宿主 OS 建立
    │
    ├── 2. 创建容器 mount namespace（隔离的文件系统视图）
    │
    ├── 3. bind-mount /mnt/steamtrain → 容器内 /mnt/steamtrain
    │        将宿主 FUSE 挂载点注入容器的 mount namespace
    │
    ├── 4. 容器进程读写 /mnt/steamtrain（透过 bind-mount → FUSE → steamtrain-client）
    │
    └── 5. 容器退出后 unmount_volume() → manifest_root
```

关键点：**FUSE 驱动在宿主 OS 运行，容器内不需要特权就能访问**，安全隔离由 bind-mount + mount namespace 保证。

---

## 六、安全边界

| 层 | 保护内容 | 机制 |
|----|---------|------|
| 传输层 | 网络窃听 | QUIC 内置 TLS 1.3 |
| 存储层 | 存储节点窥视明文 | AES-256-GCM 客户端加密（存储节点只见密文） |
| 授权层 | 未授权 Runner 访问卷 | CapToken secp256k1 签名绑定 Runner 地址 |
| 时效层 | 凭证重放 | `expires_at_block` + `nonce` 单调递增 |
| 可用性层 | 存储节点故障 | Reed-Solomon K+M 纠删码，M 节点同时故障仍可恢复 |
| 完整性层 | 跨作业数据篡改 | `manifest_root` 锚定上链（CIP-9 指令 43） |

**零信任存储节点**是 CIP-9 安全模型的核心：即使所有存储节点全部被攻陷，攻击者也只拿到密文分片，无法还原明文。密钥只存在于 Runner 进程内存中。

---

## 七、与 Runner 注册表的关系

`steamtrain-client` 的存储能力需要在 Runner 注册表（0x01）中声明（通过 `RateCard`）：

```rust
// RateCard 中的相关字段（CIP-9/10 新增）
pub steamtrain_capable: bool,         // 是否链接了 steamtrain-client
pub supports_containers: bool,        // 是否支持 OCI 容器执行
pub container_limits: Option<ContainerCapacity>,
pub allowed_image_registries: Vec<String>,
```

未声明 `steamtrain_capable: true` 的 Runner 不会被分配含 `volume_mounts` 的作业——由 CIP-2 §4 候选筛选第 8 条（Volume mount filter）保证。
