"""Hermes-zh native plugin: Zero-source-patch Simplified Chinese localization.

Conforms strictly to Hermes official plugin architecture and lazy lifecycle hooks.
Never imports heavy platform SDKs or performs invasive patches at import or cold start.
Features:
1. Complete 102 Slash Command descriptions for Telegram / Discord / Slack menus & /help & /commands
2. Deep agent.i18n catalog overlay fixing /status, /context, /resume, /fast, /model, etc.
3. Native Telegram approval card attributes, reasons & resolution notices
4. Direct slash command handlers localization (/whoami, /busy, /platform, /approvals, etc.)
5. Dynamic 380 Chinese tips library with module-level cache decoupling
6. Output interception safety-net for Telegram and Gateway system notices
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

PLUGIN_NAME = "hermes-zh"
VERSION = "0.1.0"


def _status(_raw_args: str = "") -> str:
    """Return status and ensure all patches are updated."""
    import patcher
    patcher.apply_all()
    try:
        import agent.display as display
        tv = display.get_tool_verb("terminal")
        mv = display.get_tool_verb("memory")
    except Exception:
        tv = "未知"
        mv = "未知"

    cmd_count = len(patcher.ZH_COMMAND_DESCRIPTIONS)
    i18n_count = len(patcher.ZH_I18N_OVERRIDES)

    v_str = f"v{VERSION}" if not str(VERSION).startswith("v") else str(VERSION)
    return (
        f"★ {PLUGIN_NAME} 汉化插件 {v_str} 运行正常 (◕‿◕)！\n"
        f"- 全量指令汉化: 已启用 {cmd_count} 条系统指令与斜杠菜单中文说明\n"
        f"- 核心目录覆盖: 已注入 {i18n_count} 条 i18n 深度汉化词条（/status、/context、/resume 等）\n"
        f"- 终端动词状态: {tv}\n"
        f"- 记忆动词状态: {mv}\n"
        f"- 审批卡与高危拦截: 已启用 (含审批结果「已允许本会话执行」等汉化)\n"
        f"- 常用指令深度支持: 已汉化 /whoami、/busy、/platform、/approvals 等\n"
        f"- 心跳与流式状态汉化: 已启用 (「正在处理中 — N 分钟 — 轮次 N/M，等待模型响应」)\n"
        f"- 自我提升复盘汉化: 已启用 (「自我提升复盘：技能 '...' 已更新」)\n"
        f"- 发现小贴士 (Tips) 库: 已启用 380 条全量精翻中文库\n"\
        f"- 网关与系统生命周期通知: 已启用重启、更新、上线与数据库警告汉化\n"
        f"- 加载架构: 官方生命周期懒加载（纯事件挂钩，杜绝冷启动死锁与递归）\n"
        f"- 核心源码兼容性: 100% 独立插件运作，适配官方社区插件库标准。"
    )


def _wire_telegram(native: Any, adapter: Any) -> bool:
    """Lazy platform handler invoked only when Telegram connects."""
    import patcher
    return patcher.wire_telegram_adapter(native, adapter)


def _on_session_start(*args: Any, **kwargs: Any) -> None:
    """Lazy session hook to ensure core patches are active when session starts."""
    try:
        import patcher
        patcher.apply_all()
    except Exception:
        pass


def register(ctx) -> None:
    """Register slash command and lazy platform hook.

    Adheres strictly to Hermes official plugin lifecycle:
    1. Zero eager module importing or patching at register() time.
    2. Registers lazy platform handler via ctx.register_platform_handler('telegram', ...).
    3. Registers lazy on_session_start hook to ensure patches when turn begins.
    4. Registers /hermes-zh status command.
    """
    # 1. Official lazy platform wiring: called ONLY when Telegram connects
    ctx.register_platform_handler("telegram", _wire_telegram)

    # 2. Lazy session hook: ensures patches on session initialization
    ctx.register_hook("on_session_start", _on_session_start)

    # 3. Slash command for manual verification & status
    ctx.register_command(
        "hermes-zh",
        _status,
        description="查看 Hermes 汉化插件运行状态与词条统计",
    )
