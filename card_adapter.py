"""Hermes-zh plugin: Multi-platform interactive card adapter (Telegram/Discord/Feishu/CLI).

Features:
1. Telegram native InlineKeyboardMarkup with CallbackQueryHandler.
2. Discord ActionRow & Button components with on_interaction listener.
3. Feishu (Lark) Interactive CardKit cards with card.action.trigger response.
4. Graceful fallback to pure-text output on CLI and unsupported platforms.
5. Non-blocking asynchronous update execution preserving Gateway main loop.
6. Strict zero-emoji compliance across all cards, buttons, and toast notices.

Author: Cody
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("hermes_zh.card_adapter")

PLUGIN_NAME = "hermes-zh"

# 平台标识常量
PLATFORM_TELEGRAM = "telegram"
PLATFORM_DISCORD = "discord"
PLATFORM_FEISHU = "feishu"
PLATFORM_CLI = "cli"

# 回调动作常量（严格无 emoji）
ACTION_UPDATE = "update"
ACTION_CANCEL = "cancel"

# 运行时活动 Adapter 缓存（弱耦合解耦）
_active_adapters: Dict[str, Any] = {}


def register_active_adapter(platform: str, adapter: Any) -> None:
    """注册平台的活动 Adapter 实例。"""
    key = str(platform).strip().lower()
    if key:
        _active_adapters[key] = adapter


def get_active_adapter(platform: str) -> Optional[Any]:
    """获取指定平台的活动 Adapter 实例。"""
    key = str(platform).strip().lower()
    return _active_adapters.get(key)


def clear_active_adapters() -> None:
    """清理活动 Adapter 缓存（供测试或断开重连时调用）。"""
    _active_adapters.clear()


def get_current_platform_context() -> Tuple[str, str, Optional[str]]:
    """获取当前消息会话的平台类型、Chat ID 与 Thread ID。

    通过 ContextVars 与环境变量双重探测，CLI 环境下安全回退。
    返回: (platform, chat_id, thread_id)
    """
    platform = ""
    chat_id = ""
    thread_id: Optional[str] = None

    try:
        from gateway.session_context import get_session_env
        platform = str(get_session_env("HERMES_SESSION_PLATFORM", "") or "").strip().lower()
        chat_id = str(get_session_env("HERMES_SESSION_CHAT_ID", "") or "").strip()
        raw_tid = get_session_env("HERMES_SESSION_THREAD_ID", "")
        thread_id = str(raw_tid).strip() if raw_tid else None
    except Exception:
        pass

    if not platform:
        platform = str(os.environ.get("HERMES_SESSION_PLATFORM", "")).strip().lower()
    if not chat_id:
        chat_id = str(os.environ.get("HERMES_SESSION_CHAT_ID", "")).strip()
    if thread_id is None:
        raw_tid = os.environ.get("HERMES_SESSION_THREAD_ID")
        thread_id = str(raw_tid).strip() if raw_tid else None

    # 如果无法探测到具体平台，但已连接活动 Telegram Adapter 且存在 chat_id，可作为 Telegram 会话
    if not platform and PLATFORM_TELEGRAM in _active_adapters and chat_id:
        platform = PLATFORM_TELEGRAM

    return platform or PLATFORM_CLI, chat_id, thread_id


# ============================================================================
# 1. 安全平滑异步更新与重载执行器 (Non-blocking Async Updater)
# ============================================================================

async def run_async_update(
    is_test: bool = False,
    target_version: str = "",
) -> Tuple[bool, str, str]:
    """安全平滑更新与重载执行器。

    1. 测试模式：模拟平滑更新流程，不损坏实际代码与配置；
    2. 真实模式：在后台异步子进程中调用更新，禁止阻塞主网关事件循环；
    3. 更新完成后，平滑重新应用全部补丁并重置版本缓存。

    返回: (是否成功, 说明信息, 目标版本号)
    """
    if is_test:
        # 测试模式：模拟微小异步网络耗时（0.5s），保证交互感
        await asyncio.sleep(0.5)
        new_ver = target_version or "0.1.4"
        return True, "模拟更新流程执行成功", new_ver

    # 真实更新流程
    try:
        cmd = ["hermes", "plugins", "update", PLUGIN_NAME]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        out_msg = stdout.decode("utf-8", errors="ignore").strip()
        err_msg = stderr.decode("utf-8", errors="ignore").strip()

        if proc.returncode == 0:
            # 平滑重载补丁与重置缓存
            try:
                try:
                    from . import hermes_zh_patcher as patcher
                    from . import version_checker
                except ImportError:
                    import hermes_zh_patcher as patcher
                    import version_checker
                patcher.apply_all()
                version_checker.reset_failure_cooldown()
            except Exception as e:
                logger.debug("更新后平滑重载补丁异常: %s", e)

            return True, out_msg or "插件更新成功", target_version or "最新"
        else:
            fail_reason = err_msg or out_msg or f"进程退出码 {proc.returncode}"
            return False, fail_reason, ""
    except Exception as exc:
        logger.error("真实更新执行异常: %s", exc, exc_info=True)
        return False, str(exc), ""


# ============================================================================
# 2. Telegram 原生交互卡（弹卡）适配
# ============================================================================

def build_telegram_card_text(
    current_version: str,
    latest_version: str,
    is_test: bool = False,
) -> str:
    """构造 Telegram 交互弹卡正文（严格无任何 emoji 表情）。"""
    v_curr = f"v{str(current_version).strip().lstrip('vV')}"
    v_latest = f"v{str(latest_version).strip().lstrip('vV')}"
    test_tag = " [测试模拟]" if is_test else ""
    lines = [
        f"{PLUGIN_NAME} 汉化插件{test_tag}",
        f"当前版本：{v_curr}",
        f"发现新版本：{v_latest}",
    ]
    if is_test:
        lines.append("说明：当前为测试卡片，点击下方按钮可验证真实交互流程")
    else:
        lines.append("更新建议：包含多平台交互卡适配与性能体验优化")
    return "\n".join(lines)


def build_telegram_keyboard(is_test: bool = False, target_version: str = "") -> Any:
    """构造 Telegram 原生 InlineKeyboardMarkup。"""
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        suffix = f"test:{target_version}" if is_test else f"prod:{target_version}"
        update_data = f"hermes_zh:{ACTION_UPDATE}:{suffix}"
        cancel_data = f"hermes_zh:{ACTION_CANCEL}:{suffix}"
        buttons = [
            [
                InlineKeyboardButton("立即更新", callback_data=update_data),
                InlineKeyboardButton("暂不更新", callback_data=cancel_data),
            ]
        ]
        return InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.debug("构造 Telegram InlineKeyboardMarkup 失败: %s", e)
        return None


async def handle_telegram_callback(update: Any, context: Any, adapter: Any = None) -> None:
    """处理 Telegram 交互卡按钮回调。"""
    query = getattr(update, "callback_query", None)
    if not query:
        return
    data = str(getattr(query, "data", "") or "")
    if not data.startswith("hermes_zh:"):
        return

    # 协议格式: hermes_zh:<action>:<mode>:<target_version>
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    mode = parts[2] if len(parts) > 2 else "prod"
    target_version = parts[3] if len(parts) > 3 else ""
    is_test = (mode == "test")

    # 1. 点击【暂不更新】
    if action == ACTION_CANCEL:
        try:
            await query.answer(text="已取消更新")
        except Exception:
            pass
        try:
            cancel_text = (
                f"{PLUGIN_NAME} 汉化插件\n"
                "已取消更新。如需更新可随时使用 /hermes_zh 检查。"
            )
            await query.edit_message_text(text=cancel_text, reply_markup=None)
        except Exception as exc:
            logger.debug("Telegram 卡片取消状态编辑失败: %s", exc)
        return

    # 2. 点击【立即更新】
    if action == ACTION_UPDATE:
        try:
            await query.answer(text="正在启动更新流程...")
        except Exception:
            pass

        try:
            updating_text = (
                f"{PLUGIN_NAME} 汉化插件\n"
                "正在执行平滑更新，请稍候..."
            )
            await query.edit_message_text(text=updating_text, reply_markup=None)
        except Exception as exc:
            logger.debug("Telegram 卡片更新中状态编辑失败: %s", exc)

        # 解耦异步启动更新，绝不阻断主网关循环
        asyncio.create_task(_execute_telegram_update_flow(query, is_test=is_test, target_version=target_version))


async def _execute_telegram_update_flow(query: Any, is_test: bool, target_version: str) -> None:
    """Telegram 更新执行后续状态回调。"""
    success, message, new_ver = await run_async_update(is_test=is_test, target_version=target_version)
    try:
        if success:
            display_ver = f"v{new_ver.lstrip('vV')}" if new_ver else "最新"
            done_text = (
                f"{PLUGIN_NAME} 汉化插件\n"
                f"更新成功！当前版本：{display_ver}\n"
                "插件已平滑重载生效，请在会话中继续使用。"
            )
        else:
            done_text = (
                f"{PLUGIN_NAME} 汉化插件\n"
                f"更新未完成：{message}\n"
                "提示：您也可在终端执行 hermes plugins update hermes-zh 手动更新。"
            )
        await query.edit_message_text(text=done_text, reply_markup=None)
    except Exception as exc:
        logger.debug("Telegram 更新结果卡片编辑失败: %s", exc)


def wire_telegram_card_handler(native: Any, adapter: Any) -> bool:
    """在 Telegram 平台上注册交互卡 CallbackQueryHandler。"""
    register_active_adapter(PLATFORM_TELEGRAM, adapter)
    try:
        from telegram.ext import CallbackQueryHandler

        if getattr(native, "_hermes_zh_card_handler_wired", None) is not True:
            async def _on_query(update: Any, context: Any) -> None:
                await handle_telegram_callback(update, context, adapter)

            handler = CallbackQueryHandler(_on_query, pattern=r"^hermes_zh:")
            native.add_handler(handler)
            native._hermes_zh_card_handler_wired = True
            logger.info("成功注册 Telegram 交互弹卡 CallbackQueryHandler")
        return True
    except Exception as exc:
        logger.debug("注册 Telegram CallbackQueryHandler 失败或处于非 PTB 环境: %s", exc)
        return False


async def send_telegram_card(
    chat_id: str,
    text: str,
    keyboard: Any,
    thread_id: Optional[str] = None,
    adapter: Any = None,
) -> bool:
    """向 Telegram 会话下发交互弹卡。"""
    tg_adapter = adapter or get_active_adapter(PLATFORM_TELEGRAM)
    if not tg_adapter:
        return False

    # 若未连接真实的 Bot，不强行下发，走降级纯文本路径
    if getattr(tg_adapter, "_bot", None) is None:
        return False

    try:
        send_ctrl = getattr(tg_adapter, "_send_control_message", None)
        if callable(send_ctrl):
            await send_ctrl(
                chat_id=chat_id,
                text=text,
                parse_mode=None,  # 纯文本解析避免 markdown 字符转义破坏
                thread_id=thread_id,
                metadata=None,
                reply_markup=keyboard,
            )
            return True

        send_fn = getattr(tg_adapter, "send", None)
        if callable(send_fn):
            await send_fn(chat_id=chat_id, content=text)
            return True
    except Exception as exc:
        logger.warning("下发 Telegram 交互弹卡失败: %s", exc)
        return False

    return False


# ============================================================================
# 3. Discord 平台组件卡片适配 (Message Components)
# ============================================================================

def build_discord_card_payload(
    current_version: str,
    latest_version: str,
    is_test: bool = False,
) -> Dict[str, Any]:
    """构造 Discord Message Component 交互卡（严格无任何 emoji）。"""
    v_curr = f"v{str(current_version).strip().lstrip('vV')}"
    v_latest = f"v{str(latest_version).strip().lstrip('vV')}"
    test_tag = " [测试模拟]" if is_test else ""
    lines = [
        f"{PLUGIN_NAME} 汉化插件{test_tag}",
        f"当前版本：{v_curr}",
        f"发现新版本：{v_latest}",
    ]
    if is_test:
        lines.append("说明：当前为测试卡片，点击下方按钮可验证真实交互流程")
    else:
        lines.append("更新建议：包含多平台交互卡适配与性能体验优化")

    content = "\n".join(lines)
    suffix = f"test:{latest_version}" if is_test else f"prod:{latest_version}"

    # 符合 Discord REST / Gateway ActionRow + Button 规范
    components = [
        {
            "type": 1,  # ACTION_ROW
            "components": [
                {
                    "type": 2,  # BUTTON
                    "style": 1,  # Primary (blurple)
                    "label": "立即更新",
                    "custom_id": f"hermes_zh:{ACTION_UPDATE}:{suffix}",
                },
                {
                    "type": 2,  # BUTTON
                    "style": 2,  # Secondary (grey)
                    "label": "暂不更新",
                    "custom_id": f"hermes_zh:{ACTION_CANCEL}:{suffix}",
                },
            ],
        }
    ]

    return {
        "content": content,
        "components": components,
    }


def build_discord_view(is_test: bool = False, target_version: str = "") -> Any:
    """若 discord.py SDK 可用，构造原生 discord.ui.View。"""
    try:
        import discord
        view = discord.ui.View(timeout=300)
        suffix = f"test:{target_version}" if is_test else f"prod:{target_version}"
        btn_update = discord.ui.Button(
            label="立即更新",
            style=discord.ButtonStyle.primary,
            custom_id=f"hermes_zh:{ACTION_UPDATE}:{suffix}",
        )
        btn_cancel = discord.ui.Button(
            label="暂不更新",
            style=discord.ButtonStyle.secondary,
            custom_id=f"hermes_zh:{ACTION_CANCEL}:{suffix}",
        )
        view.add_item(btn_update)
        view.add_item(btn_cancel)
        return view
    except Exception:
        return None


async def handle_discord_interaction(interaction: Any, adapter: Any = None) -> None:
    """处理 Discord 按钮交互事件。"""
    data = getattr(interaction, "data", {}) or {}
    custom_id = str(data.get("custom_id", "") or "")
    if not custom_id.startswith("hermes_zh:"):
        return

    parts = custom_id.split(":")
    action = parts[1] if len(parts) > 1 else ""
    mode = parts[2] if len(parts) > 2 else "prod"
    target_version = parts[3] if len(parts) > 3 else ""
    is_test = (mode == "test")

    response = getattr(interaction, "response", None)

    # 1. 取消更新
    if action == ACTION_CANCEL:
        cancel_text = (
            f"{PLUGIN_NAME} 汉化插件\n"
            "已取消更新。如需更新可随时使用 /hermes_zh 检查。"
        )
        try:
            if response and hasattr(response, "edit_message"):
                await response.edit_message(content=cancel_text, view=None)
        except Exception as exc:
            logger.debug("Discord 取消状态编辑失败: %s", exc)
        return

    # 2. 立即更新
    if action == ACTION_UPDATE:
        updating_text = (
            f"{PLUGIN_NAME} 汉化插件\n"
            "正在执行平滑更新，请稍候..."
        )
        try:
            if response and hasattr(response, "edit_message"):
                await response.edit_message(content=updating_text, view=None)
        except Exception as exc:
            logger.debug("Discord 更新中状态编辑失败: %s", exc)

        asyncio.create_task(_execute_discord_update_flow(interaction, is_test=is_test, target_version=target_version))


async def _execute_discord_update_flow(interaction: Any, is_test: bool, target_version: str) -> None:
    """Discord 更新执行后续状态更新。"""
    success, message, new_ver = await run_async_update(is_test=is_test, target_version=target_version)
    display_ver = f"v{new_ver.lstrip('vV')}" if new_ver else "最新"
    if success:
        done_text = (
            f"{PLUGIN_NAME} 汉化插件\n"
            f"更新成功！当前版本：{display_ver}\n"
            "插件已平滑重载生效，请在会话中继续使用。"
        )
    else:
        done_text = (
            f"{PLUGIN_NAME} 汉化插件\n"
            f"更新未完成：{message}\n"
            "提示：您也可在终端执行 hermes plugins update hermes-zh 手动更新。"
        )

    try:
        followup = getattr(interaction, "followup", None)
        if followup and hasattr(followup, "send"):
            await followup.send(content=done_text)
        elif hasattr(interaction, "edit_original_response"):
            await interaction.edit_original_response(content=done_text, view=None)
    except Exception as exc:
        logger.debug("Discord 更新结果回显失败: %s", exc)


def wire_discord_card_handler(native: Any, adapter: Any) -> bool:
    """在 Discord 平台上对接 Message Component 交互监听。"""
    register_active_adapter(PLATFORM_DISCORD, adapter)
    try:
        if getattr(native, "_hermes_zh_interaction_wired", None) is not True:
            async def _on_interaction(interaction: Any) -> None:
                await handle_discord_interaction(interaction, adapter)

            if hasattr(native, "add_listener"):
                native.add_listener(_on_interaction, "on_interaction")
                native._hermes_zh_interaction_wired = True
                logger.info("成功注册 Discord on_interaction 监听器")
                return True
    except Exception as exc:
        logger.debug("注册 Discord on_interaction 失败: %s", exc)
    return False


async def send_discord_card(
    chat_id: str,
    text: str,
    view: Any,
    adapter: Any = None,
) -> bool:
    """向 Discord 频道下发带 Message Component 的交互弹卡。"""
    dc_adapter = adapter or get_active_adapter(PLATFORM_DISCORD)
    if not dc_adapter:
        return False

    client = getattr(dc_adapter, "_client", None)
    if client is None:
        return False

    try:
        if hasattr(client, "get_channel"):
            channel = client.get_channel(int(chat_id)) if str(chat_id).isdigit() else None
            if channel and hasattr(channel, "send"):
                if view is not None:
                    await channel.send(content=text, view=view)
                else:
                    await channel.send(content=text)
                return True

        send_fn = getattr(dc_adapter, "send", None)
        if callable(send_fn):
            await send_fn(chat_id=chat_id, content=text)
            return True
    except Exception as exc:
        logger.warning("下发 Discord 交互卡失败: %s", exc)
        return False

    return False


# ============================================================================
# 4. 飞书（Feishu / Lark）卡片适配 (Interactive Card / CardKit)
# ============================================================================

def build_feishu_card_payload(
    current_version: str,
    latest_version: str,
    is_test: bool = False,
) -> Dict[str, Any]:
    """构造飞书 Interactive Card (CardKit JSON)，严格无任何 emoji。"""
    v_curr = f"v{str(current_version).strip().lstrip('vV')}"
    v_latest = f"v{str(latest_version).strip().lstrip('vV')}"
    test_tag = " [测试模拟]" if is_test else ""
    lines = [
        f"**当前版本**：{v_curr}",
        f"**发现新版本**：{v_latest}",
    ]
    if is_test:
        lines.append("说明：当前为测试卡片，点击下方按钮可验证真实交互流程")
    else:
        lines.append("更新建议：包含多平台交互卡适配与性能体验优化")

    card_content = "\n".join(lines)
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{PLUGIN_NAME} 汉化插件{test_tag}"},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": card_content},
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "立即更新"},
                        "type": "primary",
                        "value": {
                            "hermes_zh_action": ACTION_UPDATE,
                            "is_test": is_test,
                            "target_version": latest_version,
                        },
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "暂不更新"},
                        "type": "default",
                        "value": {
                            "hermes_zh_action": ACTION_CANCEL,
                            "is_test": is_test,
                            "target_version": latest_version,
                        },
                    },
                ],
            },
        ],
    }


def handle_feishu_card_action(data: Any, adapter: Any) -> Tuple[bool, Any]:
    """处理飞书卡片按钮点击回传动作 (card.action.trigger)。

    返回: (是否命中处理, 响应对象)
    """
    action_value = None
    if hasattr(data, "action") and isinstance(getattr(data.action, "value", None), dict):
        action_value = data.action.value
        event = data
    elif hasattr(data, "event"):
        event = getattr(data, "event", None)
        if hasattr(event, "action") and isinstance(getattr(event.action, "value", None), dict):
            action_value = event.action.value
        else:
            action = getattr(event, "action", None) if event else None
            action_value = getattr(action, "value", {}) or {}
    else:
        event = data
        action = getattr(event, "action", None)
        action_value = getattr(action, "value", {}) or {}

    if not isinstance(action_value, dict) or "hermes_zh_action" not in action_value:
        return False, None

    zh_action = str(action_value.get("hermes_zh_action", ""))
    is_test = bool(action_value.get("is_test", False))
    target_version = str(action_value.get("target_version", ""))
    card_resp_fn = getattr(adapter, "_card_response", None)

    # 1. 点击【暂不更新】
    if zh_action == ACTION_CANCEL:
        cancel_card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{PLUGIN_NAME} 汉化插件"},
                "template": "grey",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": "已取消更新。如需更新可随时使用 /hermes_zh 检查。"},
                }
            ],
        }
        if callable(card_resp_fn):
            return True, card_resp_fn(cancel_card)
        return True, cancel_card

    # 2. 点击【立即更新】
    if zh_action == ACTION_UPDATE:
        updating_card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{PLUGIN_NAME} 汉化插件"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": "正在执行平滑更新，请稍候..."},
                }
            ],
        }

        # 异步解耦调度更新
        loop = getattr(adapter, "_loop", None)
        if loop and not loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                _execute_feishu_update_flow(adapter, event, is_test=is_test, target_version=target_version),
                loop,
            )
        else:
            coro = _execute_feishu_update_flow(adapter, event, is_test=is_test, target_version=target_version)
            try:
                asyncio.create_task(coro)
            except RuntimeError:
                coro.close()

        if callable(card_resp_fn):
            return True, card_resp_fn(updating_card)
        return True, updating_card

    return False, None


async def _execute_feishu_update_flow(
    adapter: Any,
    event: Any,
    is_test: bool,
    target_version: str,
) -> None:
    """飞书更新执行后续通知。"""
    success, message, new_ver = await run_async_update(is_test=is_test, target_version=target_version)
    display_ver = f"v{new_ver.lstrip('vV')}" if new_ver else "最新"
    if success:
        done_text = (
            f"{PLUGIN_NAME} 汉化插件\n"
            f"更新成功！当前版本：{display_ver}\n"
            "插件已平滑重载生效，请在会话中继续使用。"
        )
    else:
        done_text = (
            f"{PLUGIN_NAME} 汉化插件\n"
            f"更新未完成：{message}\n"
            "提示：您也可在终端执行 hermes plugins update hermes-zh 手动更新。"
        )

    try:
        send_fn = getattr(adapter, "send", None)
        chat_id = getattr(event, "open_chat_id", None) or getattr(event, "chat_id", None)
        if callable(send_fn) and chat_id:
            await send_fn(chat_id=str(chat_id), content=done_text)
    except Exception as exc:
        logger.debug("飞书更新后发通知异常: %s", exc)


def wire_feishu_card_handler(native: Any, adapter: Any) -> bool:
    """在飞书平台上拦截并挂载卡片按钮回传钩子。"""
    register_active_adapter(PLATFORM_FEISHU, adapter)
    try:
        if getattr(adapter, "_hermes_zh_feishu_card_wired", None) is not True:
            orig_trigger = getattr(adapter, "_on_card_action_trigger", None)
            if callable(orig_trigger):
                def _zh_card_trigger_wrapper(data: Any) -> Any:
                    handled, resp = handle_feishu_card_action(data, adapter)
                    if handled:
                        return resp
                    return orig_trigger(data)

                adapter._on_card_action_trigger = _zh_card_trigger_wrapper
                adapter._hermes_zh_feishu_card_wired = True
                logger.info("成功挂载飞书 card.action.trigger 拦截钩子")
                return True
    except Exception as exc:
        logger.debug("挂载飞书卡片拦截失败: %s", exc)
    return False


async def send_feishu_card(
    chat_id: str,
    card_dict: Dict[str, Any],
    adapter: Any = None,
) -> bool:
    """向飞书会话下发 Interactive Card 交互弹卡。"""
    feishu_adapter = adapter or get_active_adapter(PLATFORM_FEISHU)
    if not feishu_adapter:
        return False

    client = getattr(feishu_adapter, "_client", None)
    if client is None:
        return False

    try:
        send_card_fn = getattr(feishu_adapter, "_send_interactive_card", None)
        if callable(send_card_fn):
            await send_card_fn(
                chat_id=chat_id,
                card=card_dict,
                metadata=None,
                failure_message="下发飞书更新卡片失败",
            )
            return True

        send_fn = getattr(feishu_adapter, "send", None)
        if callable(send_fn):
            import json
            await send_fn(chat_id=chat_id, content=json.dumps(card_dict, ensure_ascii=False))
            return True
    except Exception as exc:
        logger.warning("下发飞书交互卡失败: %s", exc)
        return False

    return False


# ============================================================================
# 5. 跨平台调度中枢与优雅降级 (Central Dispatcher & Graceful Fallback)
# ============================================================================

def dispatch_status(raw_args: str = "", current_version: str = "0.1.4") -> str:
    """分发 /hermes_zh 命令：多平台交互弹卡与优雅降级统一入口。

    1. 解析测试指令与强制刷新参数；
    2. 统一执行先锋源与 Curated Catalog 检测；
    3. 若检测到新版本（或处于测试模拟模式）：
       - 在 Telegram 环境下发原生 InlineKeyboardMarkup 交互卡；
       - 在 Discord 环境下发 Message Component 交互卡；
       - 在飞书环境下发 Interactive Card 消息卡；
       - 若未接入特定平台或发送不成功，自动优雅降级为纯文本输出。
    4. 若无新版本且非测试模式，返回紧凑的标准状态纯文本。
    """
    try:
        try:
            from . import version_checker
        except ImportError:
            import version_checker

        # 检查是否为强制刷新
        force_refresh = str(raw_args).strip().lower() in ("check", "refresh", "-f", "--force")
        check_res = version_checker.check_update(
            current_version=current_version,
            raw_args=raw_args,
            force_refresh=force_refresh,
        )

        # 若无新版本（且非测试模拟），直接返回标准状态纯文本
        if not check_res.has_update:
            return version_checker.format_status_message(current_version, check_res.latest_version)

        # 检测当前平台与会话定位
        platform, chat_id, thread_id = get_current_platform_context()

        # 尝试平台原生弹卡下发
        card_sent = False

        # A. Telegram 弹卡尝试
        if platform == PLATFORM_TELEGRAM and chat_id:
            tg_adapter = get_active_adapter(PLATFORM_TELEGRAM)
            if tg_adapter and getattr(tg_adapter, "_bot", None) is not None:
                card_text = build_telegram_card_text(
                    current_version=current_version,
                    latest_version=check_res.latest_version,
                    is_test=check_res.is_test,
                )
                keyboard = build_telegram_keyboard(
                    is_test=check_res.is_test,
                    target_version=check_res.latest_version,
                )
                if keyboard:
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(
                            send_telegram_card(
                                chat_id=chat_id,
                                text=card_text,
                                keyboard=keyboard,
                                thread_id=thread_id,
                                adapter=tg_adapter,
                            )
                        )
                        card_sent = True
                    except RuntimeError:
                        try:
                            asyncio.run(
                                send_telegram_card(
                                    chat_id=chat_id,
                                    text=card_text,
                                    keyboard=keyboard,
                                    thread_id=thread_id,
                                    adapter=tg_adapter,
                                )
                            )
                            card_sent = True
                        except Exception:
                            pass

        # B. Discord 弹卡尝试
        elif platform == PLATFORM_DISCORD and chat_id:
            dc_adapter = get_active_adapter(PLATFORM_DISCORD)
            if dc_adapter and getattr(dc_adapter, "_client", None) is not None:
                dc_view = build_discord_view(
                    is_test=check_res.is_test,
                    target_version=check_res.latest_version,
                )
                dc_payload = build_discord_card_payload(
                    current_version=current_version,
                    latest_version=check_res.latest_version,
                    is_test=check_res.is_test,
                )
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        send_discord_card(
                            chat_id=chat_id,
                            text=dc_payload["content"],
                            view=dc_view,
                            adapter=dc_adapter,
                        )
                    )
                    card_sent = True
                except RuntimeError:
                    try:
                        asyncio.run(
                            send_discord_card(
                                chat_id=chat_id,
                                text=dc_payload["content"],
                                view=dc_view,
                                adapter=dc_adapter,
                            )
                        )
                        card_sent = True
                    except Exception:
                        pass

        # C. 飞书弹卡尝试
        elif platform == PLATFORM_FEISHU and chat_id:
            fs_adapter = get_active_adapter(PLATFORM_FEISHU)
            if fs_adapter and getattr(fs_adapter, "_client", None) is not None:
                fs_card = build_feishu_card_payload(
                    current_version=current_version,
                    latest_version=check_res.latest_version,
                    is_test=check_res.is_test,
                )
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        send_feishu_card(
                            chat_id=chat_id,
                            card_dict=fs_card,
                            adapter=fs_adapter,
                        )
                    )
                    card_sent = True
                except RuntimeError:
                    try:
                        asyncio.run(
                            send_feishu_card(
                                chat_id=chat_id,
                                card_dict=fs_card,
                                adapter=fs_adapter,
                            )
                        )
                        card_sent = True
                    except Exception:
                        pass

        # 若原生弹卡成功分发下发，返回空字符串通知 Gateway 无需再发送重复纯文本
        if card_sent:
            return ""

        # 优雅降级：CLI、未适配平台或弹卡下发失败时，输出标准纯文本
        return version_checker.format_card_fallback_text(
            current_version=current_version,
            latest_version=check_res.latest_version,
            is_test=check_res.is_test,
        )

    except Exception as exc:
        logger.error("dispatch_status 异常降级: %s", exc, exc_info=True)
        v_str = f"v{str(current_version).strip().lstrip('vV')}"
        return (
            f"{PLUGIN_NAME} 汉化插件\n"
            f"当前版本：{v_str}\n"
            "问题反馈：https://github.com/Cody292/hermes-zh/issues"
        )
