# hermes-zh: Hermes 官方标准简体中文语言包

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version: 0.1.6](https://img.shields.io/badge/Version-0.1.7-green.svg)](https://github.com/Cody292/hermes-zh)
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

本插件只通过公开的语言包接口扩展：plugin.yaml 声明 provides_locales，并用 register_locale_dir 注册 locales/。没有运行时私有函数劫持，也没有改核心私有表。

### 核心特性

1. 官方标准语言包集成
   - 基于官方 provides_locales: ["zh"] 标准清单声明。
   - 核心静态文本 `locales/zh.yaml` 只覆盖 `approval.*` 与 `gateway.*` 的一部分（当前 261 键，不是 en.yaml 全量）。没有的键回落 Hermes 自带中文。每一条的 `{占位符}` 集合与英文源一致，不写未覆盖的覆盖率。
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

It registers Simplified Chinese only through provides_locales and register_locale_dir. No runtime monkey-patching and no private table writes.

### Key Features

1. Native Locale Pack:
   Declaratively provides the "zh" locale for the standard agent.i18n catalog.
2. Verified Key Coverage:
   Partial overlay of `approval.*` and `gateway.*` (261 keys, not the full en.yaml catalog). Placeholder sets match the English source. Unlisted keys fall back to Hermes's bundled Chinese.
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
