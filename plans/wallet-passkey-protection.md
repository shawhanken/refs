# Plan: 实现 Passkey 保护层（路径 B）

## Context

当前钱包将 secp256k1 私钥**明文存储**在 `chrome.storage.local` 中，安全风险高。目标是用 WebAuthn Passkey 保护私钥——用户需要通过指纹/面部识别才能解锁钱包。**不改链节点**，secp256k1 签名流程不变，只加密私钥的存储。

核心机制：WebAuthn **PRF 扩展**在认证时派生确定性密钥 → AES-GCM 加密私钥。

---

## 存储结构变化

```js
// 旧格式（无 passkey）— 保持向后兼容
{ account: { privateKey: '0x...', address, publicKey, name } }

// 新格式（passkey 已启用）— privateKey 字段移除
{ account: { address, publicKey, name,
    passkey: { credentialId: 'base64...', salt: 'hex...', iv: 'hex...', ciphertext: 'hex...' }
} }

// 解锁后的会话存储（chrome.storage.session）— service worker 休眠后仍保持
{ sessionKey: '0x...' }  // 解密后的私钥，浏览器关闭时自动清除
```

---

## 实施步骤

### Step 1: 新建 `src/lib/passkey.js`

WebAuthn + 加解密模块，约 120 行：

```js
// 检测 PRF 支持
export async function isPasskeySupported()
  → 检查 window.PublicKeyCredential 存在
  → 返回 boolean

// 注册 passkey（创建凭据）
export async function registerPasskey(userId)
  → navigator.credentials.create() 带 prf 扩展
  → rp: { name: "Cowboy Wallet" }  （不设 id，让浏览器用当前 origin）
  → user: { id: userId (address bytes), name: address }
  → authenticatorSelection: { residentKey: "preferred", userVerification: "required" }
  → 返回 { credentialId, prfSupported }

// 用 passkey 认证并获取 PRF 输出
export async function authenticatePasskey(credentialId, salt)
  → navigator.credentials.get() 带 prf: { eval: { first: salt } }
  → 返回 PRF 输出 (ArrayBuffer)

// AES-GCM 加密私钥
export async function encryptKey(prfOutput, privateKeyBytes)
  → HKDF(prfOutput, salt, "cowboy-wallet-key") → AES-256-GCM key
  → crypto.subtle.encrypt() → { iv, ciphertext }

// AES-GCM 解密私钥
export async function decryptKey(prfOutput, iv, ciphertext)
  → 同样的 HKDF → AES key
  → crypto.subtle.decrypt() → privateKeyBytes
```

**关键依赖**：全部使用浏览器原生 Web Crypto API（`crypto.subtle`），无需新增 npm 依赖。

### Step 2: 修改 `src/background/service-worker.js`

**KeyManager 改动**：

- `sign()` 方法：优先从 `chrome.storage.session` 读取 `sessionKey`（解密后的私钥），如果没有则尝试 `chrome.storage.local` 中的明文 `privateKey`（兼容旧格式）
- `exportPrivateKey()`：同上逻辑
- `createAccount()` / `importPrivateKey()`：行为不变（仍存明文），passkey 加密由 popup 端完成后通过新消息类型更新存储

**新增消息类型**：

| 消息类型 | 作用 |
|---------|------|
| `CHECK_PASSKEY_STATUS` | 返回 `{ enabled: boolean }`，检查 account 是否有 passkey 字段 |
| `SAVE_PASSKEY_ACCOUNT` | 接收加密后的 account 数据（含 passkey 字段，不含 privateKey），写入 storage |
| `UNLOCK` | 接收解密后的私钥 hex，存入 `chrome.storage.session.set({ sessionKey })` |
| `LOCK` | 清除 `chrome.storage.session` 中的 sessionKey |
| `CHECK_UNLOCKED` | 检查 session 中是否有 sessionKey，返回 `{ unlocked: boolean }` |

**`LOGOUT` 改动**：额外清除 `chrome.storage.session`。

### Step 3: 修改 `src/popup/popup.html`

新增两个 view（插入在 `view-welcome` 之后）：

**view-unlock**（~15 行 HTML）：
- Cowboy logo + "解锁钱包" 标题
- "使用 Passkey 解锁" 按钮（`btn-primary`）
- 错误提示区域（`error-text hidden`）

**view-passkey-setup**（~15 行 HTML）：
- "保护你的钱包" 标题
- 描述文字 + 🛡️ 图标
- "启用 Passkey 保护" 按钮（`btn-primary`）
- "暂时跳过" 按钮（`btn-text`）

**view-dashboard 改动**：
- `actions-section` 中添加一行 passkey 状态（`btn-text` 样式的 "启用 Passkey" 或 "Passkey: 已启用" 文字）

### Step 4: 修改 `src/popup/popup.js`

**初始化逻辑改动**（`DOMContentLoaded`）：

```
GET_ACCOUNT → 无账户 → view-welcome
           → 有账户 + 无 passkey 字段 → showDashboard()     // 旧行为
           → 有账户 + 有 passkey 字段 → CHECK_UNLOCKED
               → 已解锁 → showDashboard()
               → 未解锁 → show('view-unlock')
```

**新增函数**：

- `setupPasskey()` — 创建账户后调用（view-passkey-setup 页的按钮）
  1. 调用 `isPasskeySupported()` 检测
  2. 调用 `registerPasskey()` 注册凭据
  3. 调用 `authenticatePasskey()` 获取 PRF 输出
  4. 调用 `encryptKey()` 加密当前私钥
  5. 发送 `SAVE_PASSKEY_ACCOUNT` 更新存储（移除明文 privateKey，加入 passkey 字段）
  6. 发送 `UNLOCK` 将私钥存入 session
  7. 跳转到 view-backup

- `unlockWallet()` — view-unlock 页的按钮
  1. 从 account.passkey 获取 credentialId、salt
  2. 调用 `authenticatePasskey()` 获取 PRF 输出
  3. 调用 `decryptKey()` 解密
  4. 发送 `UNLOCK` 存入 session
  5. 跳转到 showDashboard()

**事件绑定**：在 `bindEvents()` 中添加新按钮的监听。

**createAccount 流程改动**：
```
现有: createAccount → view-backup → showDashboard
改为: createAccount → view-passkey-setup → (启用 passkey 或跳过) → view-backup → showDashboard
```

**importAccount 流程改动**：
```
现有: importAccount → showDashboard
改为: importAccount → view-passkey-setup → (启用 passkey 或跳过) → showDashboard
```

**Dashboard passkey 状态**：
- 未启用时显示 "启用 Passkey 保护" 文字按钮，点击进入 setupPasskey 流程
- 已启用时显示 "Passkey: 已启用" 静态文字

### Step 5: 修改 `src/popup/popup.css`

新增约 30 行样式：
```css
.unlock-content { text-align: center; padding: 24px 0; }
.unlock-icon { font-size: 48px; margin-bottom: 24px; }
.passkey-setup-content { display: flex; flex-direction: column; gap: 16px; }
.passkey-hero { text-align: center; padding: 32px 0; }
.passkey-icon { font-size: 48px; margin-bottom: 16px; }
.passkey-desc { color: var(--cowboy-text-muted); font-size: 14px; line-height: 1.6; }
.passkey-status { font-size: 12px; color: var(--cowboy-success); }
```

### Step 6: 新建测试 `src/test/passkey.test.js`

测试 `encryptKey` / `decryptKey` 的加解密对称性（使用随机密钥模拟 PRF 输出）。WebAuthn API 本身无法在 Node 环境中测试，只测加解密逻辑。

---

## 不改动的文件

- `src/lib/cbor.js` — 交易编码不变
- `src/lib/codec.js` — 提交格式不变
- `src/lib/address.js` — 地址逻辑不变
- `src/content/` — 注入和中继不变
- `src/popup/approve.js` — 审批弹窗不变
- `src/manifest.json` — `storage` 权限已覆盖 `chrome.storage.session`

---

## 验证方案

1. `npm test` — 确保现有测试 + 新加密测试通过
2. `npm run build` — 构建成功
3. Chrome 侧载测试：
   - 创建新账户 → 出现 passkey 设置页 → 启用 → 验证 chrome.storage.local 中无明文 privateKey
   - 关闭 popup 重新打开 → 出现解锁页 → 指纹认证 → 进入 dashboard
   - 发送转账 → 正常签名提交（验证 session key 工作）
   - "暂时跳过" → 验证旧流程正常（向后兼容）
   - 导入私钥 → passkey 设置 → 解锁流程
   - Logout → 清除所有数据
