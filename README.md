# hermes-zh: Hermes 官方原生简体中文汉化插件 / Simplified Chinese Localization Plugin for Hermes Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Version: 0.1.3](https://img.shields.io/badge/Version-0.1.4--dev-green.svg)](#)
[![Hermes: Plugin](https://img.shields.io/badge/Hermes-Native%20Plugin-purple.svg)](#)

[中文文档](#中文文档) | [English Documentation](#english-documentation)

---

<a name="中文文档"></a>
## 中文文档

`hermes-zh` 是专为 [Hermes Agent](https://hermes-agent.nousresearch.com/) 打造的官方原生生命周期、免改源码的 Simplified Chinese 简体中文汉化插件。

遵循 Hermes 官方插件规范与生命周期挂钩设计，严格遵守无死锁、抗重入、懒加载与模块解耦准则，为 Telegram、Discord、Slack 等平台及终端 CLI 提供完整的本土化中文体验。

### 核心特性

#### 1. 102 条全量斜杠指令中文菜单
- **Telegram 原生指令菜单**：在 Telegram 输入 `/` 呼出菜单时，全部 102 条内置与常用系统指令均展示地道、流畅的中文说明与参数提示。
- **/help 与 /commands 全面汉化**：无论是分页指令目录还是分类帮助提示，均呈现规范的中文文档。

#### 2. 网关核心指令与元数据深度汉化
- **/status 网关状态面板**：会话 ID、标题、创建时间、最近活动、模型渠道、累计计费 Token、代理运行状态、连接平台（Telegram、Webhook 等）全部纯正中文呈现。
- **/context 上下文深度看板**：模型名称、窗口总容量、当前占用比例、距上限余量、自动压缩阈值、压缩次数与节省比例、多轮累计吞吐量（输入/输出/思考）全面中文化。
- **/resume 会话恢复与 /fast 极速模式**：多房间作用域拦截、权限提示、会话编号列表、极速通道状态等提示语完全覆盖。
- **/whoami 身份凭据**：当前平台、私聊/群组作用域、权限级别（管理员/普通用户）、可执行斜杠指令列表中文渲染。
- **/busy 忙碌响应行为**：清晰解释排队 (queue)、动态注入 (steer) 与立即中断 (interrupt) 机制。
- **/platform 平台适配器监控**：各平台连接、重试、暂停状态与操作指引中文展示。

#### 3. 高危命令审批卡与原因拦截
- **声明式模板属性覆盖**：优雅替换 Telegram 审批卡标题、放行按钮（[允许一次]、[本会话允许]、[永久允许]、[拒绝]）与 Toast 提示气泡。
- **高危命令原因精准转译**：涵盖破坏性递归删除、根目录路径操作、危险提权、Fork 炸弹、敏感密钥读取、Docker 变更、动态代码执行等 30+ 类高危原因。
- **审批结果通知**：优雅汉化「已允许本次会话执行」、「已拒绝执行」、「审批已过期」等实时卡片状态。

#### 4. 实时动态心跳与工具动词
- **流式处理心跳**：例如「正在处理中 — 2 分钟 — 轮次 3/500，等待模型响应 (流式)」。
- **工具执行标签 (Tool Verbs)**：涵盖 `terminal` (正在运行终端命令)、`execute_code` (正在执行Python代码)、`read_file` (正在读取文件)、`browser_exec` (正在操作浏览器)、`memory` (正在更新记忆) 等 30+ 种工具动词与预览构建器。
- **自我提升复盘**：后台复盘摘要实时呈现「自我提升复盘：技能 'xxx' 已更新 · 记忆库已更新」。

#### 5. 发现小贴士 (Tips) 380 条全量精翻库
- 内置 `tips_zh.json`，全量精翻官方 380 条命令行使用技巧与高阶功能说明。
- 采用**模块级独立缓存解耦架构**，兼顾出口文本动态拦截与 CLI 启动随机推荐，彻底规避外部库未加载时的静默失效。

---

### 架构设计与规范

本插件严格遵循 Hermes 原生插件开发规范：
1. **杜绝冷启动硬开**：严禁在 `__init__.py` 顶层导入重型网络库或打补丁，所有平台定制统一通过 `ctx.register_platform_handler("telegram", ...)` 由官方连接成功时回调注入。
2. **遵守异步协程契约**：严格保持所有适配器协程的 `async def` 签名与参数完整传递，绝不引发未捕获的事件循环异常。
3. **官方模板属性优先**：优先使用官方 `_EA_HEADER`、`_EA_ACTION_LABELS` 插槽，绝不暴力覆写核心底层事件回调。
4. **单向防重入保护 (Anti-Recursion Guard)**：在所有适配器与 Mixin 方法挂钩处设置单向布尔标志，杜绝递归死循环引发 `RecursionError`。
5. **双层拦截防御 (Defense-in-Depth)**：
   - **内层**：动态注入 `agent.i18n` 运行时词典覆盖 (`patch_i18n()`) 与 `COMMAND_REGISTRY` 指令集；
   - **外层**：在适配器出口 `translate_telegram_content()` 执行兜底模式匹配，即使系统底座更新或存在硬编码英文也能确保用户端 100% 汉化。

---

### 安装与启用

#### 方式 1：社区快捷安装（推荐）
```bash
# 通过 GitHub 快捷安装
hermes plugins install Cody292/hermes-zh

# 或通过完整 Git 仓库 URL 安装
hermes plugins install https://github.com/Cody292/hermes-zh.git
```

#### 方式 2：官方插件命令行启用
```bash
# 启用插件（推荐关闭 tool-override 模式）
hermes plugins enable hermes-zh --no-allow-tool-override
```

#### 方式 3：配置文件启用
在 `~/.hermes/config.yaml` 中配置：
```yaml
display:
  language: zh

plugins:
  enabled:
    - hermes-zh
  entries:
    hermes-zh:
      allow_tool_override: false
```

---

### 验证与诊断

#### 1. 运行插件合规体验证
```bash
hermes plugins validate <path-to-hermes-zh>
```

#### 2. 在对话中验证运行状态
在终端或 Telegram 对话中发送：
```text
/hermes-zh
```
将即时返回插件版本、已启用的指令条数、i18n 覆盖数及各模块动词状态。

---

<a name="english-documentation"></a>
## English Documentation

`hermes-zh` is a native, zero-source-modification Simplified Chinese localization plugin designed for [Hermes Agent](https://hermes-agent.nousresearch.com/).

Built strictly against Hermes official plugin specifications and lifecycle hooks, it implements lazy loading, anti-recursion guards, and modular decoupling to deliver an authentic, idiomatic Chinese experience across Telegram, Discord, Slack, and terminal CLI environments.

### Key Features

#### 1. Full 102 Slash Commands Localized Menu
- **Native Slash Menu on Telegram**: Typing `/` reveals all 102 built-in and system commands with idiomatic Simplified Chinese descriptions and parameter hints.
- **Complete `/help` & `/commands` Localization**: Categorized help hints and paginated command catalogues rendered in clean Chinese.

#### 2. Deep Localization of Core Gateway Commands
- **/status Gateway Dashboard**: Session ID, title, creation time, activity timestamp, model channel, cumulative tokens, agent state, and connected platforms (Telegram, Webhook, etc.) completely localized.
- **/context Deep Inspection**: Model identifier, context window size, current utilization percentage, headroom margin, automatic compression threshold, compression ratio, and token throughput (prompt, completion, thinking) translated accurately.
- **/resume & /fast**: Multi-room room-scoped restrictions, permission notifications, session pickers, and fast-mode toggles.
- **/whoami & /busy**: User identity, scope permissions, executable commands list, and busy steering/queue explanations.

#### 3. Command Approval Cards & Risk Reason Interception
- **Declarative Template Overrides**: Localizes Telegram approval card headers, interactive action buttons ([Allow Once], [Allow for Session], [Allow Forever], [Deny]), and toast notifications.
- **Accurate High-Risk Explanations**: 30+ categories of dangerous command patterns translated (recursive deletions, root directory operations, privilege escalations, fork bombs, secret exposure risks, docker modifications, dynamic code execution).
- **Resolution Status Alerts**: Real-time card statuses such as "Allowed for this session", "Denied", and "Approval expired".

#### 4. Real-time Dynamic Heartbeats & Tool Verbs
- **Streaming Heartbeat**: e.g., "Processing — 2m — Turn 3/500, waiting for model response (streaming)".
- **Tool Verbs & Previews**: Over 30 tool action verbs including `terminal` (Running command), `execute_code` (Executing Python code), `read_file` (Reading file), `browser_exec` (Controlling browser), and `memory` (Updating memory).
- **Self-Improvement Reviews**: Instant post-turn reflections (e.g., "Self-Improvement: Skill updated · Memory updated").

#### 5. Curated Library of 380 Tips
- Bundled with `tips_zh.json`, providing 380 high-quality translated CLI tips and power-user tricks.
- Decoupled module-level cache architecture ensuring reliable dynamic output interception and random CLI startup suggestions.

---

### Architecture & Principles

- **No Eager Import on Cold Start**: Heavy modules and monkey patches are never loaded at `__init__.py` top-level. Adapters register via `ctx.register_platform_handler("telegram", ...)` upon successful gateway connection.
- **Asynchronous Coroutine Contract**: Preserves full `async def` signatures and parameter forwarding.
- **Template Slot Priority**: Overrides official slots (`_EA_HEADER`, `_EA_ACTION_LABELS`) without clobbering foundational event loops.
- **Anti-Recursion Guard**: Uses boolean lock flags across mixins to eliminate recursion loops.
- **Defense-in-Depth**:
  - **Inner Layer**: Runtime injection into `agent.i18n` and `COMMAND_REGISTRY`.
  - **Outer Layer**: Exit pipeline fallback matching via `translate_telegram_content()`.

---

### Installation & Quick Start

#### Method 1: Community Quick Install (Recommended)
```bash
# Install via GitHub shortcut
hermes plugins install Cody292/hermes-zh

# Or install via full Git URL
hermes plugins install https://github.com/Cody292/hermes-zh.git
```

#### Method 2: CLI Enable
```bash
hermes plugins enable hermes-zh --no-allow-tool-override
```

#### Method 3: Configuration File
Add to `~/.hermes/config.yaml`:
```yaml
display:
  language: zh

plugins:
  enabled:
    - hermes-zh
  entries:
    hermes-zh:
      allow_tool_override: false
```

---

### Verification & Diagnostics

#### Validate Plugin Manifest
```bash
hermes plugins validate <path-to-hermes-zh>
```

#### Check Plugin Status in Chat
Send in chat or terminal:
```text
/hermes-zh
```
Displays loaded version, localized command count, and active verb hooks.

---

### License

This project is licensed under the [MIT License](LICENSE).
Contributions and community issues are welcome!
