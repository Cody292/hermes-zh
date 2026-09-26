# hermes-zh: Hermes 官方原生简体中文汉化插件

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version: 0.1.4](https://img.shields.io/badge/Version-0.1.4-green.svg)](https://github.com/Cody292/hermes-zh)
[![Hermes: Native Plugin](https://img.shields.io/badge/Hermes-Native%20Plugin-purple.svg)](https://hermes-agent.nousresearch.com/)
[![Requires: Hermes >=0.19](https://img.shields.io/badge/Requires-Hermes%20%3E%3D0.19-blueviolet.svg)](https://github.com/NousResearch/hermes-agent)

[中文说明](#中文说明) | [English Documentation](#english-documentation)

---

## 目录

- [中文说明](#中文说明)
  - [项目定位](#项目定位)
  - [核心特性](#核心特性)
  - [工作原理与架构](#工作原理与架构)
  - [安装与启用](#安装与启用)
  - [命令指南与交互卡](#命令指南与交互卡)
  - [验证与诊断](#验证与诊断)
  - [设计准则与安全规范](#设计准则与安全规范)
  - [常见问题与故障排查](#常见问题与故障排查)
- [English Documentation](#english-documentation)
  - [Overview](#overview)
  - [Key Features](#key-features)
  - [How It Works and Architecture](#how-it-works-and-architecture)
  - [Installation and Quick Start](#installation-and-quick-start)
  - [Commands and Interactive Cards](#commands-and-interactive-cards)
  - [Validation and Diagnostics](#validation-and-diagnostics)
  - [Architecture Principles](#architecture-principles)
  - [Troubleshooting and FAQ](#troubleshooting-and-faq)
- [开源协议与致谢](#开源协议与致谢)

---

## 中文说明

### 项目定位

hermes-zh 是专为 [Hermes Agent](https://hermes-agent.nousresearch.com/) 打造的原生生命周期、免改源码的 Simplified Chinese 简体中文汉化插件。

插件严格基于 Hermes 官方插件体系契约设计，遵循纯懒加载、无死锁、抗重入与模块解耦准则。在完全零侵入底座源码的前提下，为 Telegram、Discord、飞书 (Feishu) 等即时通讯平台以及终端 CLI 控制台提供专业、流畅、地道的本土化中文交互体验。

### 核心特性

#### 1. 全量 102 条斜杠指令中文菜单
- Telegram 原生指令菜单：在客户端输入 "/" 即可唤出完整中文指令列表，覆盖全部 102 条内置指令与系统功能，参数与说明一目了然。
- /help 与 /commands 深度汉化：结构化分类帮助目录与分页展示均呈现地道中文排版，告别原生英文碎片化体验。

#### 2. 网关指令与元数据深度看板
- /status 网关运行状态：会话 ID、标题、创建时间、最近活动、模型渠道、累计计费 Token、代理运行状态、连接平台（Telegram、Webhook 等）全部纯正中文呈现。
- /context 深度上下文看板：模型名称、上下文窗口总容量、当前占用比例、余量空间、自动压缩阈值、压缩次数与节省比例、多轮累计吞吐量（输入、输出、思考）完整汉化。
- /resume 会话恢复与 /fast 极速模式：多房间作用域拦截、权限提示、历史会话选择器及极速模式通道切换提示语完整覆盖。
- /whoami 身份凭据与权限：当前会话平台、用户 ID、私聊或群组作用域、操作权限级别及可执行指令列表中文渲染。
- /busy 忙碌响应机制：清晰解析排队 (queue)、动态注入 (steer) 与立即中断 (interrupt) 的运行状态。
- /platform 平台适配器监控：各端连接状态、重试机制、运行状态及异常指引清晰可见。

#### 3. 高危命令审批卡与原因拦截
- 声明式模板覆盖：优雅替换 Telegram 与终端高危审批卡标题、交互按钮（[允许一次]、[本会话允许]、[永久允许]、[拒绝]）与操作气泡提示。
- 30+ 类危险操作模式精准转译：深入覆盖危险提权、递归破坏性删除、根目录变动、Fork 炸弹、敏感密钥泄露、Docker 容器变更及动态代码注入等场景。
- 审批状态与生命周期通知：实时同步并汉化「已允许本次会话执行」、「已拒绝执行」、「审批已过期」及超时倒计时提醒。

#### 4. 实时动态心跳与工具动词 (Tool Verbs)
- 流式处理心跳：实时展示当前轮次与用时，例如「正在处理中 — 2 分钟 — 轮次 3/500，等待模型响应 (流式)」。
- 30+ 常用工具动词中文化：涵盖 terminal (正在运行终端命令)、execute_code (正在执行Python代码)、read_file (正在读取文件)、browser_exec (正在操作浏览器)、memory (正在更新记忆) 等。
- 自我提升复盘：后台自我复盘摘要实时呈现「自我提升复盘：技能 'xxx' 已更新 · 记忆库已更新」。

#### 5. 发现小贴士 (Tips) 380 条全量精翻库
- 深度精翻官方 380 条 CLI 使用技巧与高级功能指南，内置独立缓存管理。
- 采用模块级独立解耦架构，兼顾文本动态拦截与 CLI 启动随机推荐，杜绝外部库未加载时的静默失效。

#### 6. 多端交互弹卡与平滑更新
- 原生交互组件支持：在 Telegram (Inline Keyboard)、Discord (Message Component) 及飞书 (Interactive Card) 中无缝渲染更新卡片。
- 一键检查与更新：通过 /hermes-zh 指令一键唤出版本卡片，在线查询官方最新版本并执行平滑重载。
- 本地开发模式保护：自动识别本地开发工作区，防止错误触发官方远程拉取逻辑。

### 工作原理与架构

hermes-zh 严格遵守 Hermes 插件隔离与生命周期钩子规范，其核心工作流如下：

```text
[Hermes 启动 / 网关就绪]
          |
          v
[register() 入口] ---> 注册平台回调 (Telegram / Discord / 飞书)
          |        ---> 注册会话钩子 (on_session_start)
          |        ---> 注册指令路由 (/hermes-zh, /hermes_zh)
          |
          +---> [纯懒加载保障] 绝不在加载顶层引入重型模块或执行网络请求
          |
[用户会话发起]
          |
          v
[on_session_start] ---> 激活核心补丁 apply_all()
          |                  |
          |                  +---> 内层注入: 覆盖 agent.i18n 运行时字典
          |                  +---> 指令注入: 覆盖 COMMAND_REGISTRY 中文说明
          |                  +---> 模板注入: 挂载审批卡与超时提示属性
          v
[平台消息流转] ---> 适配器出口 translate_telegram_content() 兜底
          |
          +---> 遇到未覆盖的系统通知或硬编码英文字符执行正则模式匹配
          +---> 确保终端与即时通讯端呈现 100% 地道中文
```

### 安装与启用

#### 1. 通过官方插件市场安装（推荐）

直接在终端执行：

```bash
hermes plugins install Cody292/hermes-zh
```

或者使用完整 Git 仓库地址：

```bash
hermes plugins install https://github.com/Cody292/hermes-zh.git
```

#### 2. 在配置文件中启用

编辑 `~/.hermes/config.yaml`，添加或确保包含以下配置项：

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

#### 3. 命令行手动启用

```bash
hermes plugins enable hermes-zh --no-allow-tool-override
```

### 命令指南与交互卡

#### 指令语法

在 Telegram、Discord、飞书或控制台终端中发送：

```text
/hermes-zh [参数]
```

（注：也可使用下划线别名 `/hermes_zh`）

#### 支持参数

| 参数 | 说明 | 示例 |
| :--- | :--- | :--- |
| (无参数) | 查询当前插件运行状态、版本号及官方最新版本 | `/hermes-zh` |
| `check` / `refresh` | 强制穿透 6 小时本地缓存，向官方插件库发起实时检测 | `/hermes-zh check` |
| `test` / `mock` | 进入开发者测试模式，模拟新版本交互弹卡与更新流 | `/hermes-zh test` |

#### 跨平台交互弹卡行为

- Telegram：下发带有 [立即更新] 和 [取消] 的 Inline 键盘，点击后触发异步更新任务并实时回显重载结果。
- Discord：下发带交互按钮的 Message Component，支持一键确认或取消更新。
- 飞书 (Feishu)：推送交互式富文本卡片，支持用户直接在移动端或桌面端卡片内完成版本维护。
- 终端 CLI：降级为纯文本格式输出，清晰展示当前版本、线上版本以及手动更新命令。

### 验证与诊断

#### 1. 运行官方插件合规体验证

```bash
hermes plugins validate path/to/hermes-zh
```

#### 2. 在对话中验证运行状态

在任意受支持的平台对话框发送 `/hermes-zh`，系统将返回如下格式的诊断信息：

```text
hermes-zh 汉化插件
当前版本：v0.1.4
官方版本：v0.1.4
状态：已是最新版本
问题反馈：https://github.com/Cody292/hermes-zh/issues
```

#### 3. 执行自动化测试套件

插件内置全面的单元测试与模拟验证集：

```bash
pytest tests/
```

### 设计准则与安全规范

1. 杜绝冷启动性能损耗：在 `__init__.py` 顶层坚决不导入重型网络库或打猴子补丁（Monkey Patch）。所有平台适配器统一延迟到平台真实建立连接时的回调函数中注入。
2. 遵守异步协程契约：严格保持底层适配器协程的 `async def` 签名与参数链条完整传递，不破坏主线程事件循环。
3. 官方模板属性优先：优先使用官方暴露的模板插槽（如 `_EA_HEADER`、`_EA_ACTION_LABELS`），不直接覆盖底层不可控事件回路。
4. 防重入保护机制：在所有适配器方法与 Mixin 挂钩处设立单向布尔防重入锁，根除循环嵌套调用导致的 `RecursionError`。
5. 双层防御体系 (Defense-in-Depth)：
   - 内层防御：通过 `patch_i18n()` 注入底层词典及重写 `COMMAND_REGISTRY`；
   - 外层防御：通过出口过滤器兜底翻译未收录的硬编码文本，即使底层版本小幅变动也能保障输出中文的一致性。
6. 安全沙箱与版本合规：统一且仅以 Hermes 官方 Curated Catalog 为准绳，版本比对网络超时严格限制在 1.5 秒以内并具备 60 秒故障冷却保护，不阻断正常业务。

### 常见问题与故障排查

#### Q: 安装后输入 "/" 菜单没有显示中文指令？
- 检查 `~/.hermes/config.yaml` 中是否已将 `hermes-zh` 加入 `plugins.enabled` 列表。
- 重启 Hermes 服务或重新连接 Telegram 网关以使指令注册表刷新。

#### Q: 提示「当前为本地开发版，官方更新命令仅适用于通过 hermes plugins install 安装的官方社区版」？
- 说明当前插件直接运行于本地 Git 源码工作区，而非经由官方包管理器拉取的发行版。
- 在本地开发环境下，可直接通过 `git pull` 更新代码；如需测试弹卡逻辑，可附加 `test` 参数：`/hermes-zh test`。

#### Q: 如何反馈翻译不准确或漏译的问题？
- 欢迎在 GitHub 提交 Issue：[hermes-zh Issues](https://github.com/Cody292/hermes-zh/issues)。请附带截屏及相关指令名称。

---

## English Documentation

### Overview

`hermes-zh` is a native, zero-source-modification Simplified Chinese localization plugin purpose-built for [Hermes Agent](https://hermes-agent.nousresearch.com/).

Built strictly around the official Hermes plugin specification, it adheres strictly to lazy-loading, anti-recursion guards, deadlock-free execution, and modular decoupling. It delivers an idiomatic, comprehensive Chinese experience across Telegram, Discord, Feishu, and terminal CLI environments without changing a single line of Hermes core source code.

### Key Features

- **Full 102 Slash Command Menus**: Complete Chinese descriptions for all built-in commands when typing "/" on Telegram, along with fully formatted `/help` and `/commands` views.
- **Deep Gateway Dashboards**: Comprehensive localization of `/status`, `/context`, `/resume`, `/fast`, `/whoami`, `/busy`, and `/platform`.
- **High-Risk Approval Interception**: Full translation of dangerous command categories (privilege escalations, recursive deletions, credential exposure, etc.) and action buttons ([Allow Once], [Allow for Session], [Allow Forever], [Deny]).
- **Dynamic Heartbeats & Tool Verbs**: Chinese tool execution status (terminal, execute_code, read_file, browser_exec, memory) and real-time self-improvement review notices.
- **380 Curated Tips**: Full Chinese translation of official CLI tips with decoupled caching.
- **Interactive Multi-Platform Cards**: Native action cards on Telegram, Discord, and Feishu with in-chat version checking and smooth reload.

### How It Works and Architecture

`hermes-zh` strictly respects Hermes lifecycle isolation:

```text
[Hermes Startup]
       |
       v
[register(ctx)] ---> Register platform handlers (Telegram, Discord, Feishu)
       |        ---> Register session hook (on_session_start)
       |        ---> Register slash commands (/hermes-zh, /hermes_zh)
       |
       +---> Zero eager heavy imports or network calls on cold start
       |
[Session Started]
       |
       v
[on_session_start] ---> Apply patches (patcher.apply_all())
       |                     |
       |                     +---> Inner Layer: patch agent.i18n & COMMAND_REGISTRY
       |                     +---> Slot Layer: override approval templates & action labels
       v
[Platform Pipeline] ---> Exit filter: translate_telegram_content() fallback
```

### Installation and Quick Start

#### 1. Official Plugin Catalog (Recommended)

```bash
hermes plugins install Cody292/hermes-zh
```

Or via full repository URL:

```bash
hermes plugins install https://github.com/Cody292/hermes-zh.git
```

#### 2. Configuration Setup

In `~/.hermes/config.yaml`:

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

#### 3. CLI Enable

```bash
hermes plugins enable hermes-zh --no-allow-tool-override
```

### Commands and Interactive Cards

Run in chat or terminal:

```text
/hermes-zh [command]
```

(Alias `/hermes_zh` is also registered)

| Argument | Description | Example |
| :--- | :--- | :--- |
| (none) | Check current plugin status and official latest version | `/hermes-zh` |
| `check` / `refresh` | Force bypass 6h local cache and query official catalog | `/hermes-zh check` |
| `test` / `mock` | Isolated developer test mode for interactive card simulation | `/hermes-zh test` |

### Validation and Diagnostics

Run official manifest and capability validation:

```bash
hermes plugins validate path/to/hermes-zh
```

Run test suite:

```bash
pytest tests/
```

### Architecture Principles

1. Zero Cold Start Penalty: Avoid heavy network or module imports at `__init__.py` top-level. Adapters wire lazily upon platform connection.
2. Async Coroutine Contract: Maintain original `async def` signatures and parameter propagation.
3. Template Slot Priority: Use official slots (`_EA_HEADER`, `_EA_ACTION_LABELS`) without breaking underlying event listeners.
4. Anti-Recursion Guards: Lock recursion loops with boolean flags across mixins.
5. Defense-in-Depth: Inner dictionary overlay plus exit-pipeline fallback regex.
6. Strict Official Catalog Alignment: Network timeout capped at 1.5s with 6h TTL caching and 60s failure backoff cooldown.

### Troubleshooting and FAQ

- **Q: Commands menu does not show Chinese after installation?**
  Restart your Hermes gateway or session to trigger command registry rebuild.
- **Q: "Local development mode" warning on update?**
  When developing in a cloned repository, run `git pull` directly. Use `/hermes-zh test` to inspect interactive update cards.

---

## 开源协议与致谢

- 本项目基于 [MIT License](LICENSE) 协议开源。
- 感谢 [Nous Research](https://nousresearch.com/) 团队创建优秀的 Hermes Agent 项目与插件生态。
