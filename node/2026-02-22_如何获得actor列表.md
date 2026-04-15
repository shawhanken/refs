# 如何获得 Actor 列表

当前链上**没有**“列出所有 actor”的 RPC 或存储 API，只能按地址查单个 actor。可用方式如下。

---

## 1. 已知地址时：查单个 Actor（RPC）

Validator 的 RPC 提供按地址查询（address 为 **hex 字符串**，无 `0x` 前缀）：

```bash
# 查某个 actor 信息
curl -s "http://localhost:4000/actor/<actor_address_hex>"
```

例如查 Runner Registry：

```bash
curl -s "http://localhost:4000/actor/478b8e507e0bb2b18c0f9e0824769e8562d10df9abe2e774896f82b4b4405266"
```

返回 JSON 包含：`address`、`code_hash`、`balance`、`nonce`、`mailbox_count`、`storage` 等。

---

## 2. 系统 Actor「列表」（5 个固定地址）

系统内置的 5 个 runner 相关 actor 的地址由 `SystemActorAddresses` 按固定规则生成，可直接用下列地址逐个请求 `/actor/{address}`，相当于“系统 actor 列表”：

| 名称 | 地址 (hex) |
|------|------------|
| runner_registry | `478b8e507e0bb2b18c0f9e0824769e8562d10df9abe2e774896f82b4b4405266` |
| job_dispatcher | `5925ba86e2189444a6c3b437b25d2ef35daecd1abf82c5fb36060f9fc0af428c` |
| result_verifier | `ec8924090e507c2d8371d2fb0bf965d553e6e5756aeec6c274df3801cf2b49b9` |
| secrets_manager | `1c0c1c72c52dbd38c741a2c1989e02a41b388348011566b914a1ed6932b8f880` |
| tee_verifier | `737fc7b9e5b280bbe625e9f85c668584092d0fd899fb2d83763b296b6b069a50` |

在项目里打印上述 5 个地址：

```bash
cd /home/ubuntu/workspace/node
cargo run -p cowboy-runner --bin print_system_actors
```

若要“列表”效果，可循环请求上述 5 个地址的 `GET /actor/{address}`。

---

## 3. 用户部署的 Actor

用户部署的 actor 地址由部署交易决定：`derive_actor_address(deployer, salt, code_hash)`。  
通常**部署脚本会打印 actor 地址**（如 `chain/examples/candle_up_down/deploy.sh` 部署后会输出），保存该地址后同样用：

```bash
curl -s "http://localhost:4000/actor/<你保存的地址hex>"
```

若未保存，只能从**区块/交易历史**中查找包含 `DeployActor` 的交易并反推地址；当前没有“按类型列出所有已部署 actor”的 RPC。

---

## 小结

| 需求 | 做法 |
|------|------|
| 查**系统 actor** | 用上述 5 个固定地址，或运行 `cargo run -p cowboy-runner --bin print_system_actors` 得到列表后，逐个 `GET /actor/{address}` |
| 查**已知地址**的 actor | `curl "http://localhost:4000/actor/<address_hex>"` |
| **“所有 actor”列表** | 当前 RPC/存储**没有**“列出全部 actor”的接口，只能通过已知地址（系统 + 部署时记录的）逐个查 |

若后续需要新增 `GET /actors` 之类的列表接口，需在存储层支持对 actor 的 key 迭代，再在 RPC 层暴露。
