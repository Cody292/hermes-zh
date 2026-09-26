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
7. Structured and categorized /help command formatting
8. Comprehensive approval timeout and lifecycle notice localization
9. Official Curated Catalog aligned version checking with TTL cache & cross-platform prompt
10. Multi-platform interactive card adapter for Telegram, Discord, Feishu with smooth update & test support
"""
from __future__ import annotations

from typing import Any

try:
    from . import hermes_zh_patcher as patcher
except ImportError:
    import hermes_zh_patcher as patcher

__all__ = ["register", "patcher"]

PLUGIN_NAME = "hermes-zh"
VERSION = "0.1.4"


def _status(_raw_args: str = "") -> str:
    """Return concise plugin status, trigger interactive cards, or show issue feedback URL."""
    patcher.apply_all()
    try:
        try:
            from . import card_adapter
        except ImportError:
            import card_adapter
        return card_adapter.dispatch_status(_raw_args, current_version=VERSION)
    except Exception:
        v_str = f"v{VERSION}" if not str(VERSION).startswith("v") else str(VERSION)
        return (
            f"{PLUGIN_NAME} 汉化插件\n"
            f"当前版本：{v_str}\n"
            "问题反馈：https://github.com/Cody292/hermes-zh/issues"
        )


def _wire_telegram(native: Any, adapter: Any) -> bool:
    """Lazy platform handler invoked only when Telegram connects."""
    return patcher.wire_telegram_adapter(native, adapter)


def _wire_discord(native: Any, adapter: Any) -> bool:
    """Lazy platform handler invoked only when Discord connects."""
    return patcher.wire_discord_adapter(native, adapter)


def _wire_feishu(native: Any, adapter: Any) -> bool:
    """Lazy platform handler invoked only when Feishu connects."""
    return patcher.wire_feishu_adapter(native, adapter)


def _on_session_start(*args: Any, **kwargs: Any) -> None:
    """Lazy session hook to ensure core patches are active when session starts."""
    try:
        patcher.apply_all()
    except Exception:
        pass


def register(ctx) -> None:
    """Register slash commands and lazy platform hooks.

    Adheres strictly to Hermes official plugin lifecycle:
    1. Zero eager module importing or patching at register() time.
    2. Registers lazy platform handlers for Telegram, Discord, and Feishu.
    3. Registers lazy on_session_start hook to ensure patches when turn begins.
    4. Registers /hermes-zh and /hermes_zh slash commands.
    """
    # 1. Official lazy platform wiring: called ONLY when platforms connect
    ctx.register_platform_handler("telegram", _wire_telegram)
    ctx.register_platform_handler("discord", _wire_discord)
    ctx.register_platform_handler("feishu", _wire_feishu)

    # 2. Lazy session hook: ensures patches on session initialization
    ctx.register_hook("on_session_start", _on_session_start)

    # 3. Slash commands for quick lookup & status (hyphen & underscore aliases)
    ctx.register_command(
        "hermes-zh",
        _status,
        description="查看汉化插件版本与反馈链接",
    )
    ctx.register_command(
        "hermes_zh",
        _status,
        description="查看汉化插件版本与反馈链接",
    )

    # 4. Ensure command registry entry for autocomplete and menu discovery
    try:
        patcher.patch_plugin_command_registration()
    except Exception:
        pass
    try:
        patcher.patch_telegram_menu_priority()
    except Exception:
        pass
