# 白皮书历史归档（_archive_）

> ## ⚠️ 这个目录里的文档**不是权威**
>
> 这些是被取代的旧版白皮书，**只用于追溯「当时怎么写的」**。
> 当前版本在上一层 [`refs/whitepaper/`](../)，权威顺序是
> **代码 > 修正案（`refs/analysis/*amendments*`）> `cowboy/docs/cips/` 的 CIP > 白皮书**。
>
> 本文件此前写着「这是所有技术决策的最终依据、优先级 🔴 最高」—— 那是本目录尚未归档时的说法，
> 现已失效（2026-09-21 更正）。

---

## 当前版本在哪

| 主题 | 当前档 |
|---|---|
| 核心技术白皮书 | [`../cowboy-technical-whitepaper.md`](../cowboy-technical-whitepaper.md) |
| 存储白皮书 | [`../cowboy-storage-whitepaper.md`](../cowboy-storage-whitepaper.md) |
| 机密白皮书 | [`../cowboy-secrets-whitepaper.md`](../cowboy-secrets-whitepaper.md) |
| 设计决策 | [`../cowboy-design-decisions.md`](../cowboy-design-decisions.md) |
| 修订日志 | [`../changelog.md`](../changelog.md) |

---

## 本目录内容

**早期核心白皮书**（被 `../cowboy-technical-whitepaper.md` 取代）

- `Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_CN.md` — 中文版
- `Cowboy_An_Actor-Model_Layer1 with Verifiable_Off-Chain_Compute_EN.md` — 英文版
- `2026-03-21_cowboy-technical-whitepaper-revised.md` — 3 月修订版
- `2026-03-21_cowboy-technical-whitepaper-revised-v2.md` — 3 月修订版 v2

**SDK 人体工程学建议**（提案性质，非规范）

- `..._(Sugguestion-SDK Ergonomics)_v2.md`
- `..._(Sugguestion-SDK Ergonomics)_v3_EN.md`

**被同名新版取代的专题白皮书**

- `cowboy-storage-whitepaper.md` / `.pdf`
- `2026-05-03_cowboy-secrets-whitepaper.md` / `.pdf`
- `cowboy-design-decisions.md`
- `changelog.md`

---

## 术语提醒

归档版本中的 **"Steamtrain"** 指的是现在的 **CBFS**（`cbfs/` repo，CIP-9 RAS 存储层）。
归档版本中的系统 actor 地址多半已失效 —— 以
[`refs/wiki/entities/system-actors.md`](../../wiki/entities/system-actors.md) 或
`node/runner/src/system_actors.rs` 为准。
