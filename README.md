# hermes-zh: Hermes 官方标准简体中文语言包

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version: 0.3.0](https://img.shields.io/badge/Version-0.3.0-green.svg)](https://github.com/Cody292/hermes-zh)
[![Hermes: Language Pack](https://img.shields.io/badge/Hermes-Language%20Pack-purple.svg)](https://hermes-agent.nousresearch.com/)
[![Requires: Hermes >=0.19](https://img.shields.io/badge/Requires-Hermes%20%3E%3D0.19-blueviolet.svg)](https://github.com/NousResearch/hermes-agent)

[中文说明](#中文说明) | [English Documentation](#english-documentation)

---

## 目录

- [中文说明](#中文说明)
  - [项目定位](#项目定位)
  - [核心特性](#核心特性)
  - [架构规范与合规设计](#架构规范与合规设计)
  - [安装与启用](#安装与启用)
  - [验证与质量门禁](#验证与质量门禁)
- [English Documentation](#english-documentation)
  - [Overview](#overview)
  - [Key Features](#key-features)
  - [Architecture and Compliance](#architecture-and-compliance)
  - [Installation](#installation)
  - [Validation](#validation)
- [开源协议与致谢](#开源协议与致谢)

---

## 中文说明

### 项目定位

hermes-zh 是专为 Hermes Agent 打造的官方标准声明式 Simplified Chinese (简体中文) 语言包插件。

本插件严格遵循 Hermes Plugin Catalog Rule 9 (上游优先准则与目录准入规范)，完全基于官方 agent.i18n 体系构建，采用声明式 provides_locales 与 register_locale_dir 机制，无任何运行时私有函数劫持或核心表篡改。

### 核心特性

1. 官方标准语言包集成
   - 基于官方 provides_locales: ["zh"] 标准清单声明。
   - 核心静态文本字典 locales/zh.yaml 100% 对齐官方 en.yaml 键集合，零孤立死键。
   - 零运行时侵入，零性能损耗，零异步调度阻塞。

2. 关键业务表面本土化覆盖
   - 安全审批交互: 覆盖 dangerous_header、choose_long、timeout、allowed_*、denied 等标准审批提示与参数文案。
   - 网关运行状态: 覆盖 /status、/context、/model、/agents 等状态面板与上下文度量提示。
   - 会话控制流: 覆盖 /resume、/reset、/compress、/goal 等核心操作的反馈与生命周期通知。

3. 规范退避机制
   - 针对上游尚未开放正规扩展点的动态文案，严格遵循退避原则保留英文原貌，坚决杜绝私自猴子补丁。

### 架构规范与合规设计

- 纯净入口: __init__.py 仅包含标准的 register_locale_dir 调用，绝不注册多余自定义命令。
- 零私有重绑: 彻底移除全部运行时函数重定向与私有字典写入。
- 门禁完备: 严格通过 hermes plugins validate、pytest 与 plugin-box release --dry-run 三道硬门禁。

### 安装与启用

通过官方插件市场安装:
```bash
hermes plugins install hermes-zh
```

配置语言偏好:
```bash
hermes config set locale zh
```

---

## English Documentation

### Overview

hermes-zh is the official declarative Simplified Chinese (zh) language pack for Hermes Agent.

It strictly adheres to Hermes Plugin Catalog Rule 9, implementing declarative locale provision via provides_locales and register_locale_dir without any runtime monkey-patching or private internal modifications.

### Key Features

1. Native Locale Pack:
   Declaratively provides the "zh" locale for the standard agent.i18n catalog.
2. Verified Key Coverage:
   100% key parity with core en.yaml for approval prompts and gateway messages.
3. Clean Architecture:
   Zero private object mutation, zero custom commands, clean lifecycle.

### Installation

```bash
hermes plugins install hermes-zh
hermes config set locale zh
```

---

## 开源协议与致谢

- 遵循 MIT 开源许可证。
- 作者: Cody (Cody292)
