# Cowboy Wallet UI Redesign — Dark AI-Era Theme

## Context
当前钱包 UI 是浅色主题、基础卡片布局，视觉上较为普通。需要全面重新设计为深色、未来感、AI 时代风格的界面，使之与 Cowboy 面向 AI 时代的定位吻合。目标：Phantom 钱包级别的质感 + 赛博朋克 AI 美学。

## Critical Files
- `src/popup/popup.css` — 主样式文件（完全重写）
- `src/popup/popup.html` — 主 HTML（字体链接 + emoji 替换为 SVG）
- `src/popup/approve.html` — 审批弹窗（字体链接 + 内联样式更新）
- `src/popup/popup.js` — 仅在需要 innerHTML 替代 textContent 时微调
- `src/popup/approve.js` — 同上

## Design System

### Color Palette (Dark Theme)
```
--cowboy-bg:            #0A0B0F        (深蓝黑背景)
--cowboy-bg-secondary:  #12131A
--cowboy-surface:       #1A1B26        (卡片/输入框背景)
--cowboy-surface-hover: #22243A
--cowboy-orange:        #F0951F        (品牌色保留，作为发光强调)
--cowboy-orange-hover:  #FFB04A
--cowboy-orange-glow:   rgba(240, 149, 31, 0.25)
--cowboy-cyan:          #00E5FF        (AI 辅助色)
--cowboy-purple:        #A855F7        (渐变辅助色)
--cowboy-text:          #E8E9ED        (主文字)
--cowboy-text-muted:    #6B7189
--cowboy-text-bright:   #FFFFFF
--cowboy-border:        rgba(255, 255, 255, 0.06)
--cowboy-success:       #34D399
--cowboy-error:         #F87171
--cowboy-glass:         rgba(255, 255, 255, 0.05)  (毛玻璃)
--cowboy-glass-border:  rgba(255, 255, 255, 0.08)
```

### Typography
- 标题字体：`Space Grotesk`（替换 DM Serif Display，更科技感）
- 正文字体：`Inter`（保留）
- 等宽字体：`JetBrains Mono`（保留）
- h1: font-weight 600, letter-spacing -0.02em
- h2: font-weight 500

### Visual Effects
- **毛玻璃卡片**：`backdrop-filter: blur(16px)` + 半透明背景 + 微妙边框
- **发光按钮**：渐变背景 + hover 时 box-shadow 发光
- **网格背景**：`repeating-linear-gradient` 创建微妙网格纹理
- **微动画**：fade-in 视图切换、shimmer logo、pulse-glow、hover 上浮

## Implementation Steps

### Step 1: popup.css — 完全重写
1. 替换 `:root` 变量为深色主题
2. `body` 加深色背景 + 网格纹理 + 自定义滚动条
3. `#app` / `.view` 更新基础样式
4. Typography 更新（Space Grotesk, font-weight 调整）
5. 按钮系统重写：
   - `.btn-primary`：`linear-gradient(135deg, #F0951F, #FF6B35)` + glow hover
   - `.btn-secondary`：透明 + glass border + orange hover
   - 所有其他按钮类更新为深色主题
6. 输入框：深色 surface 背景 + focus glow ring
7. 所有组件样式逐一更新颜色（welcome、dashboard、send、sign、export、rpc、result、history、loading、toast）
8. 卡片元素加 glassmorphism
9. Balance 值加渐变文字效果
10. Network badge 改为半透明橙色 pill
11. Status dot connected 改为 cyan
12. 新增动画 keyframes：shimmer, pulse-glow, fade-in, glow-border
13. Logo 加发光 + shimmer 伪元素
14. Input autofill 暗色适配
15. `.view:not(.hidden)` 加 fade-in 动画

### Step 2: popup.html — 更新
1. Google Fonts 链接替换（DM Serif Display → Space Grotesk:wght@500;600;700）
2. 替换所有 emoji 为 inline SVG 图标（Lucide/Feather 风格）：
   - 📋 → clipboard SVG（btn-copy-address, btn-backup-copy, btn-export-copy）
   - 🔄 → refresh SVG（btn-tx-refresh）
   - 🔑 → key SVG（export view h2）
   - ⚙️ → gear SVG（rpc view h2）
   - ⚠️ → alert-triangle SVG（backup view h2）
   - 🔒 → shield-lock SVG（unlock-icon, 48px）
   - 🛡️ → shield SVG（passkey-icon, 48px）
   - ✅ Confirm → 去掉 emoji，仅文字 "Confirm"
3. 保持所有 element ID 不变

### Step 3: approve.html — 更新
1. Google Fonts 链接替换
2. 内联 `<style>` 块全部更新为深色主题
3. approve 按钮去掉 emoji
4. glassmorphism 应用到 approve-details

### Step 4: popup.js / approve.js — 微调（如需）
- 如果 result-icon 需要 SVG，将 `textContent` 改为 `innerHTML`
- 最小化 JS 改动，仅限 UI 渲染相关

### Step 5: 验证
- `npm run build` 构建
- 检查 360x520 尺寸下所有 11 个视图渲染正确
- 确认 backdrop-filter 在 Chrome 扩展中生效
- 确认所有 JS 功能不受影响（ID 和 class 未变）

## Constraints
- 纯 vanilla CSS + HTML，无框架
- 不改 JS 消息协议、element ID、class name
- 360x520px popup 尺寸不变
- build 系统直接拷贝 popup.css，所有样式在一个文件中
