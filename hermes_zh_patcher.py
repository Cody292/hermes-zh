"""Hermes Simplified Chinese Localization Module (Production Grade & Anti-Recursion).

Safe, lazy-loaded runtime localization conforming to Hermes official plugin architecture.
Features:
1. Tool execution verbs (agent.display._TOOL_VERBS) & smart Chinese preview builders
2. Complete 102 Slash Command descriptions for Telegram / Discord / Slack menu & /help & /commands
3. Native Telegram approval card attributes, reasons & resolution notices ("Approved for session by ...")
4. Deep agent.i18n catalog overlay for /status, /context, /resume, /fast, /model, etc.
5. Direct slash command handlers localization (/whoami, /busy, /platform, /approvals, etc.)
6. Output interception safety-net for Telegram and Gateway system messages
7. Long-running heartbeat and progress messages localization
8. Background review summaries ("Self-improvement review: ...") localization
9. Dynamic Tips library localization (380 Chinese tips) with module cache decoupling
10. Zero monkey-patching of core async dispatch loops; 100% idempotent & anti-recursion safe.
"""
from __future__ import annotations

import asyncio
from contextlib import suppress
import html as _html
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger("hermes_zh")

# 1. Comprehensive tool execution labels in streaming and UI
ZH_TOOL_VERBS: dict[str, str] = {
    "web_search": "正在搜索网络",
    "web_extract": "正在阅读网页",
    "browser_navigate": "正在浏览网页",
    "browser_click": "正在点击网页",
    "browser_type": "正在输入内容",
    "browser_exec": "正在操作浏览器",
    "browser_vault_list": "正在读取保险库凭据",
    "browser_vault_fill": "正在填充保险库凭据",
    "browser_vault_save_login": "正在保存站点登录凭据",
    "browser_vault_enter_code": "正在处理双重验证码",
    "browser_vault_unlock": "正在解锁密码管理器",
    "read_file": "正在读取文件",
    "write_file": "正在写入文件",
    "patch": "正在编辑文件",
    "search_files": "正在搜索文件",
    "terminal": "正在运行终端命令",
    "execute_code": "正在执行Python代码",
    "image_generate": "正在生成图片",
    "video_generate": "正在生成视频",
    "text_to_speech": "正在生成语音",
    "vision_analyze": "正在分析图像",
    "session_search": "正在搜索历史会话",
    "skill_view": "正在查看技能",
    "skills_list": "正在查看技能列表",
    "skill_manage": "正在管理技能",
    "delegate_task": "正在委派子任务",
    "cronjob_manage": "正在管理计划任务",
    "clarify": "正在询问用户",
    "memory": "正在更新记忆",
    "todo_list": "正在更新待办清单",
    "process_manage": "正在管理后台进程",
    "computer_use": "正在操作桌面",
    "tool_search": "正在搜索扩展工具",
    "tool_describe": "正在读取工具说明",
    "tool_call": "正在调用扩展工具",
}

# 2. Reason translation dictionary
EXACT_REASON_MAP: dict[str, str] = {
    "dangerous command": "高风险敏感指令",
    "delete in root path": "根目录路径文件删除（破坏性高危操作）",
    "recursive delete": "递归删除文件或目录（破坏性删除）",
    "recursive delete (long flag)": "递归删除文件或目录 (--recursive)",
    "recursive delete (flags after operands)": "递归删除文件或目录（参数后置）",
    "format filesystem": "格式化文件系统（清盘操作）",
    "disk copy": "底层磁盘写入/复制 (dd)",
    "write to block device": "直接写入底层块设备 (/dev/sd*)",
    "SQL DROP": "数据库表/库删除操作 (SQL DROP)",
    "SQL DELETE without WHERE": "无 WHERE 条件的批量数据删除 (SQL DELETE)",
    "SQL TRUNCATE": "清空数据库表 (SQL TRUNCATE)",
    "overwrite system config": "覆盖系统核心配置文件",
    "stop/restart system service": "停止或重启系统核心服务 (systemctl)",
    "kill all processes": "强制终止所有系统进程 (kill -9 -1)",
    "force kill processes": "强制终止系统进程 (pkill/killall -9)",
    "fork bomb": "检测到 Fork 炸弹攻击代码",
    "access to SSH keys": "访问或读取系统 SSH 密钥文件",
    "access to Hermes secrets": "访问或读取 Hermes 敏感密钥配置",
    "world/other-writable permissions": "赋予全部用户全局可写权限 (chmod 777)",
    "recursive chown to root": "递归更改目录所有权为 root 用户",
    "pipe remote content to shell": "直接通过管道将远程脚本输入 Shell 执行",
    "execute remote script via process substitution": "通过进程替换直接执行远程脚本",
    "execute remote content via command substitution": "通过命令替换执行远程下载内容",
    "command parser limit exceeded": "命令长度超过安全解析器上限",
    "command parser limit or malformed executable payload": "命令异常或超过解析器安全上限",
    "stop/restart hermes gateway via shell-spliced verb (kills running agents)": "停止/重启 Hermes 网关（会导致当前会话中断）",
    "script execution via -e/-c flag": "通过 -e / -c 参数动态执行脚本",
    "script execution via heredoc": "通过 Heredoc 动态执行多行脚本",
    "shell command via -c/-lc flag": "通过 Shell -c/-lc 参数执行动态命令",
}


def translate_reason(desc: str) -> str:
    """Translate command approval reason to clean Simplified Chinese."""
    if not desc:
        return "高风险敏感指令"
    if desc in EXACT_REASON_MAP:
        return EXACT_REASON_MAP[desc]

    desc_l = desc.lower()
    if "execute_code" in desc_l or "arbitrary local python" in desc_l:
        return "Python 独立代码执行（脚本包含子进程/文件修改/系统调用，单次运行需人工授权）"
    if "root path" in desc_l or "delete in root" in desc_l:
        return "根目录路径文件删除操作（高风险文件删除）"
    if "recursive delete" in desc_l or "remove-item" in desc_l or "destructive delete" in desc_l:
        return "递归删除文件或目录（破坏性删除）"
    if "crontab" in desc_l:
        return "定时任务 (Crontab) 修改操作"
    if "docker" in desc_l:
        return "Docker 容器或镜像生命周期变更"
    if "gateway" in desc_l and ("restart" in desc_l or "stop" in desc_l or "kill" in desc_l):
        return "停止或重启 Hermes 网关（会导致当前会话中断）"
    if "security scan" in desc_l or "tirith" in desc_l:
        return f"安全防护策略拦截: {desc}"
    if "arbitrary program execution" in desc_l:
        return "通过外部程序执行任意命令"
    if "kill" in desc_l or "terminate" in desc_l:
        return "强制终止系统运行进程"
    if "package install" in desc_l or "pip install" in desc_l or "apt" in desc_l:
        return "系统软件包或环境依赖安装"
    if "sql" in desc_l:
        return "数据库高风险修改/清空操作"
    if "chmod" in desc_l or "chown" in desc_l or "permission" in desc_l:
        return "修改系统文件权限或所有者"

    return f"高风险敏感操作: {desc}"


# 3. Background review action summary localization
REVIEW_PATTERNS = [
    (r"Skill '([^']+)' patched(\s*\(.*?\))?", r"技能 '\1' 已更新\2"),
    (r"Skill '([^']+)' created(\s*\(.*?\))?", r"技能 '\1' 已创建\2"),
    (r"Skill '([^']+)' rewritten(\s*\(.*?\))?", r"技能 '\1' 已重写\2"),
    (r"Skill '([^']+)' written(\s*\(.*?\))?", r"技能 '\1' 已写入\2"),
    (r"Skill '([^']+)' removed(\s*\(.*?\))?", r"技能 '\1' 已移除\2"),
    (r"Skill '([^']+)' deleted(\s*\(.*?\))?", r"技能 '\1' 已删除\2"),
    (r"Memory updated", r"记忆库已更新"),
    (r"User profile updated", r"用户画像已更新"),
    (r"Proposal staged:\s*(.*)", r"已暂存合并提案: \1"),
]


def translate_review_summary(summary: str) -> str:
    """Translate background review actions."""
    if not isinstance(summary, str):
        return summary
    res = summary
    for pat, rep in REVIEW_PATTERNS:
        res = re.sub(pat, rep, res, flags=re.IGNORECASE)
    return res


# 4. Approval resolution messages localization
APPROVAL_RESOLVE_PATTERNS = [
    (r"✅ Approved for session by ([^\n<]+)", r"✅ \1 已允许本会话执行"),
    (r"✅ Approved once by ([^\n<]+)", r"✅ \1 已允许本次单次执行"),
    (r"✅ Approved permanently by ([^\n<]+)", r"✅ \1 已永久允许执行"),
    (r"❌ Denied by ([^\n<]+)", r"❌ \1 已拒绝执行"),
    (r"🔒 Always approve by ([^\n<]+)", r"🔒 \1 已永久允许"),
    (r"❌ Cancelled by ([^\n<]+)", r"❌ \1 已取消"),
    (r"Resolved by ([^\n<]+)", r"✅ \1 已处理"),
    (r"<i>Awaiting typed response from ([^\n<]+)…</i>", r"<i>等待 \1 输入回复…</i>"),
    (r"Awaiting typed response from ([^\n<]+)…", r"等待 \1 输入回复…"),
]


def translate_approval_resolution(text: str) -> str:
    """Translate approval resolution status and follow-ups."""
    if not isinstance(text, str):
        return text

    if "Approval expired" in text:
        return "⌛ 审批已过期 — 当前无等待执行的命令（可能已超时自动拒绝或已在其他终端处理）。"

    res = text
    for pat, rep in APPROVAL_RESOLVE_PATTERNS:
        res = re.sub(pat, rep, res)
    return res


# 5. Toast labels for callback button clicks
TOAST_LABEL_MAP: dict[str, str] = {
    "✅ Approved for session": "✅ 已允许本会话",
    "✅ Approved once": "✅ 仅允许一次",
    "✅ Approved permanently": "✅ 已永久允许",
    "❌ Denied": "❌ 已拒绝",
    "⌛ Approval expired": "⌛ 审批已过期",
    "Resolved": "已处理",
    "🔒 Always approve": "🔒 永久允许",
    "❌ Cancelled": "❌ 已取消",
    "⛔ You are not authorized to approve commands.": "⛔ 您无权审批此命令。",
    "This approval has already been resolved.": "该审批已处理完毕。",
    "Invalid approval data.": "无效的审批请求。",
    "⛔ You are not authorized to answer this prompt.": "⛔ 您无权回复此提示。",
    "This prompt has already been resolved.": "该提示已处理完毕。",
    "✏️ Type your answer in the chat.": "✏️ 请在聊天框中输入您的回复。",
    # Model/choice picker callback toasts.
    "Picker expired — use /model again.": "选择卡片已失效 — 请重新输入 /model",
    "Picker expired — run the command again.": "选择卡片已失效 — 请重新运行指令",
    "Picker expired.": "选择卡片已失效",
    "Provider not found.": "未找到该提供商",
    "Invalid selection.": "无效的选择",
    "Invalid model index.": "无效的模型序号",
    "Invalid page.": "无效页码",
    "Switch failed.": "切换失败",
    "Model switched!": "模型已切换！",
    "Confirm model selection": "请确认模型选择",
    "Group not found.": "未找到该提供商分组",
    "⛔ You are not authorized to change this setting.": "⛔ 您无权更改此设置",
}


def translate_toast_label(text: str) -> str:
    """Translate toast popup messages."""
    return TOAST_LABEL_MAP.get(text, text)


# Telegram's InlineKeyboardButton/InlineKeyboardMarkup instances are immutable
# in python-telegram-bot.  Keep all card localization in pure helpers and
# rebuild changed SDK objects instead of mutating them in place.
_PICKER_BUTTON_LABEL_MAP: dict[str, str] = {
    "◀ Prev": "◀ 上一页",
    "Next ▶": "下一页 ▶",
    "◀ Back": "◀ 返回",
    "✗ Cancel": "✗ 取消",
    "Switch anyway": "仍要切换",
    "Approve Once": "允许一次",
    "Always Approve": "总是允许",
    "Cancel": "取消",
    "Update Now": "立即更新",
    "Dismiss": "忽略",
    "Later": "稍后",
    "✓ Yes": "✓ 是",
    "✗ No": "✗ 否",
    "✏️ Other (type answer)": "✏️ 其他（输入回复）",
}

_PICKER_TEXT_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("⚙ *Model Configuration*", "⚙ *模型配置*"),
    ("⚙ _Model Configuration_", "⚙ _模型配置_"),
    ("Current model:", "当前模型:"),
    ("Provider family:", "提供商分组:"),
    ("Provider:", "提供商:"),
    ("Select a provider:", "请选择提供商:"),
    ("Select a model:", "请选择模型:"),
    ("Model selection cancelled.", "已取消模型选择。"),
    ("☤ *Update needs your input:*", "☤ *更新需要您的确认：*"),
    ("☤ _Update needs your input:_", "☤ _更新需要您的确认：_"),
    ("☤ Update prompt answered: Yes", "☤ 更新已确认：是"),
    ("☤ Update prompt answered: No", "☤ 更新已确认：否"),
    ("Update prompt answered: Yes", "更新已确认：是"),
    ("Update prompt answered: No", "更新已确认：否"),
)
_PICKER_MORE_RE = re.compile(
    r"(?P<open>\\?_)(?P<count>\d+) more available — type `/model <name>` directly(?P<close>\\?_)"
)
_PICKER_PAGE_RE = re.compile(
    r"(?P<open>\\?)\((?P<start>\d+)[–-](?P<end>\d+)\s+of\s+(?P<total>\d+)\)(?P<close>\\?)"
)
_CODE_TOKEN_RE = re.compile(r"(```[\s\S]*?```|`[^`\r\n]*?`)")
_LITERAL_NEWLINE_RE = re.compile(r"\\+n")


def sanitize_literal_newlines(text: str) -> str:
    """Safely convert accidental literal '\n' sequences into real newlines.

    Protects fenced code blocks and inline backticks so valid code examples
    aren't corrupted, while repairing prompts, cards, and notices where
    YAML/Python escaping left literal '\n' characters.
    """
    if not isinstance(text, str) or r"\n" not in text:
        return text

    tokens = _CODE_TOKEN_RE.split(text)
    cleaned = []
    for token in tokens:
        if token.startswith("`") and token.endswith("`"):
            cleaned.append(token)
        else:
            cleaned.append(_LITERAL_NEWLINE_RE.sub("\n", token))
    return "".join(cleaned)


def translate_picker_text(text: str) -> str:
    """Translate fixed English labels used by Telegram control cards.

    The helper accepts both raw Markdown (``*bold*``) and already formatted
    MarkdownV2 (``_bold_`` with escaped parentheses/underscores), because the
    initial picker calls ``format_message`` before handing its build result to
    the shared prompt sender.
    """
    if not isinstance(text, str):
        return text
    result = sanitize_literal_newlines(text)
    for source, target in _PICKER_TEXT_REPLACEMENTS:
        result = result.replace(source, target)

    def _more(match: re.Match[str]) -> str:
        return (
            f"{match.group('open')}还有 {match.group('count')} 个可用模型 — "
            f"也可直接输入 `/model <名称>`{match.group('close')}"
        )

    result = _PICKER_MORE_RE.sub(_more, result)

    def _page(match: re.Match[str]) -> str:
        return (
            f"{match.group('open')}(第 {match.group('start')}–{match.group('end')} 项，共 "
            f"{match.group('total')} 项){match.group('close')}"
        )

    return _PICKER_PAGE_RE.sub(_page, result)


def _translate_picker_button_text(text: Any) -> Any:
    if not isinstance(text, str):
        return text
    direct = _PICKER_BUTTON_LABEL_MAP.get(text)
    if direct is not None:
        return direct
    # Slash-confirm buttons carry a semantic emoji prefix in the native card;
    # preserve that visual cue while translating only the English label.
    for prefix in ("✅ ", "🔒 ", "❌ "):
        if text.startswith(prefix):
            translated = _PICKER_BUTTON_LABEL_MAP.get(text[len(prefix):])
            if translated is not None:
                return prefix + translated
    return text


def _clone_picker_button(button: Any, text: str) -> Any:
    """Clone an immutable button with a new label, preserving callback data."""
    try:
        from telegram import InlineKeyboardButton
    except Exception:
        InlineKeyboardButton = None

    data: Optional[dict[str, Any]] = None
    to_dict = getattr(button, "to_dict", None)
    if callable(to_dict):
        try:
            raw = to_dict()
            if isinstance(raw, dict):
                data = dict(raw)
        except Exception:
            data = None
    if data is not None:
        data["text"] = text
        if InlineKeyboardButton is not None:
            try:
                return InlineKeyboardButton(**data)
            except Exception:
                pass
        try:
            return type(button)(**data)
        except Exception:
            pass

    callback_data = getattr(button, "callback_data", None)
    try:
        return type(button)(text=text, callback_data=callback_data)
    except Exception:
        try:
            return type(button)(text)
        except Exception:
            # Test doubles and third-party button wrappers occasionally expose
            # a mutable copy protocol but no constructor accepting kwargs.
            try:
                from copy import copy
                clone = copy(button)
                setattr(clone, "text", text)
                return clone
            except Exception:
                return button


def translate_telegram_keyboard(keyboard: Any) -> Any:
    """Return a localized copy of an inline keyboard without mutating SDK objects."""
    if keyboard is None:
        return None
    rows = getattr(keyboard, "inline_keyboard", None)
    if rows is None:
        return keyboard

    changed = False
    translated_rows: list[list[Any]] = []
    for row in rows:
        translated_row: list[Any] = []
        for button in row:
            old_text = getattr(button, "text", None)
            new_text = _translate_picker_button_text(old_text)
            if new_text != old_text:
                changed = True
                button = _clone_picker_button(button, new_text)
            translated_row.append(button)
        translated_rows.append(translated_row)
    if not changed:
        return keyboard

    try:
        from telegram import InlineKeyboardMarkup
        return InlineKeyboardMarkup(translated_rows)
    except Exception:
        try:
            return type(keyboard)(translated_rows)
        except Exception:
            try:
                return type(keyboard)(inline_keyboard=translated_rows)
            except Exception:
                return keyboard


def _translate_prompt_build_result(built: Any) -> Any:
    """Translate the shared ``_send_prompt`` build tuple, if one was returned."""
    if not isinstance(built, tuple) or len(built) < 2:
        return built
    values = list(built)
    if isinstance(values[0], str):
        values[0] = translate_picker_text(values[0])
    values[1] = translate_telegram_keyboard(values[1])
    return tuple(values)


class _LocalizedCallbackQuery:
    """Read-only proxy that localizes callback answers/edits without touching PTB objects."""

    __slots__ = ("_query",)

    def __init__(self, query: Any):
        self._query = query

    def __getattr__(self, name: str) -> Any:
        return getattr(self._query, name)

    async def answer(self, *args: Any, **kwargs: Any) -> Any:
        args = list(args)
        if "text" in kwargs and isinstance(kwargs["text"], str):
            kwargs["text"] = translate_toast_label(kwargs["text"])
        elif args and isinstance(args[0], str):
            args[0] = translate_toast_label(args[0])
        return await self._query.answer(*args, **kwargs)

    async def edit_message_text(self, *args: Any, **kwargs: Any) -> Any:
        args = list(args)
        if "text" in kwargs and isinstance(kwargs["text"], str):
            kwargs["text"] = translate_picker_text(kwargs["text"])
        elif args and isinstance(args[0], str):
            args[0] = translate_picker_text(args[0])
        if "reply_markup" in kwargs:
            kwargs["reply_markup"] = translate_telegram_keyboard(kwargs["reply_markup"])
        return await self._query.edit_message_text(*args, **kwargs)


# 6. Busy acknowledgement headings & tails
BUSY_HEAD_MAP = {
    "⏩ Steered into current run": "⏩ 已注入当前任务",
    "↪ Redirected current run": "↪ 已重定向当前任务",
    "⏳ Subagent working": "⏳ 子任务执行中",
    "⏳ Compressing context": "⏳ 正在压缩上下文",
    "⏳ Queued for the next turn": "⏳ 已加入下轮队列",
    "⚡ Interrupting current task": "⚡ 正在中断当前任务",
}

BUSY_TAIL_MAP = {
    ". Your message arrives after the next tool call.": "。您的消息将在下一次工具调用后送达。",
    ". I'll adjust using your correction.": "。我将根据您的修正进行调整。",
    ". I'll respond once the current task finishes.": "。当前任务完成后我将立即回复。",
    ". I'll respond to your message shortly.": "。我将尽快回复您的消息。",
}

# 7. Session Info Card and Reset notices localization
SESSION_INFO_MAP = [
    (r"◆\s*Model:\s*", "◆ 模型: "),
    (r"◆\s*Provider:\s*", "◆ 渠道: "),
    (r"◆\s*Context:\s*", "◆ 上下文: "),
    (r"◆\s*Endpoint:\s*", "◆ 接口端点: "),
    (r"\btokens \(detected\)", "Token (自动检测)"),
    (r"\btokens \(config\)", "Token (配置文件)"),
    (r"\btokens \(default — set model\.context_length in config to override\)", "Token (默认 — 可在配置中设置 model.context_length 覆盖)"),
    (r"(\d+(?:\.\d+)?[KMG]?)\s+tokens\b", r"\1 Token"),
]

AUTO_RESET_PATTERNS = [
    (r"◐\s*Session reset after being stopped\.\s*Conversation history cleared\.", "◐ 会话在停止后已重置，历史记录已清除。"),
    (r"Use /resume to browse and restore a previous session\.", "输入 /resume 可浏览并恢复之前的会话。"),
]

# 7.1 Lifecycle & System Notices localization
SYSTEM_NOTICES_PATTERNS: list[tuple[str, str]] = [
    (r"♻\s*(?:Gateway|Hermes)\s*(?:restarted successfully|is back online)\.\s*Your session continues\.", "♻ 网关重启成功，您的会话已恢复继续。"),
    (r"♻️\s*(?:Gateway|Hermes)\s*online\s*—\s*Hermes is back and ready\.", "♻️ 网关已上线 — Hermes 已就绪。"),
    (r"Inference:\s*Nous free tier \(nous/welcome\)\.\s*Sign in for more:\s*/login", "推理服务：Nous 免费层 (nous/welcome)。登录以获取更多权限：/login"),
    (r"(?i)⚠️\s*(?:Gateway|Hermes)\s*(?:is\s*)?restarting\s*—\s*your current task will be interrupted\.\s*Send any message after (?:the\s*)?restart and I'll try to resume where you left off\.", "⚠️ Hermes 正在重启 — 当前任务将被中断。重启后发送任意消息，我将尝试为您恢复现场。"),
    (r"(?i)⚠️\s*(?:Gateway|Hermes)\s*(?:is\s*)?shutting down\s*—\s*your current task will be interrupted\.(?:\s*When it is back online, send any message and I'll try to pick up where we left off\.)?", "⚠️ Hermes 正在关闭 — 当前任务将被中断。恢复在线后发送任意消息，我将尝试为您恢复现场。"),
    (r"✅\s*Hermes update finished successfully\.", "✅ Hermes 更新成功完成。"),
    (r"✅\s*Hermes update finished\.", "✅ Hermes 更新已完成。"),
    (r"❌\s*Hermes update failed\.\s*Check the gateway logs or run `hermes update` manually for details\.", "❌ Hermes 更新失败。请检查网关日志或手动运行 `hermes update` 查看详情。"),
    (r"❌\s*Hermes update failed\.", "❌ Hermes 更新失败。"),
    (r"⚠️\s*Session database corruption detected\.\s*Messages may not be persisted\.\s*Recovery options:", "⚠️ 检测到会话数据库损坏，消息可能无法持久化保存。恢复选项："),
    (r"⚠️\s*Session database reported a corruption error confined to the search index", "⚠️ 会话数据库报告搜索索引局部损坏"),
    (r"⚠️\s*Session database unavailable\s*—\s*messages may not be persisted\.", "⚠️ 会话数据库不可用 — 消息可能无法持久化保存。"),
    (r"(?i)☤\s*Update prompt answered:\s*Yes", "☤ 更新确认：已选择「是」"),
    (r"(?i)☤\s*Update prompt answered:\s*No", "☤ 更新确认：已选择「否」"),
    (r"(?i)Update prompt answered:\s*Yes", "更新确认：已选择「是」"),
    (r"(?i)Update prompt answered:\s*No", "更新确认：已选择「否」"),
    (r"(?i)Already on the latest version\.", "当前已是最新版本。"),
    (r"(?i)No updates available\.", "暂无可用更新。"),
    (r"(?i)Updating Hermes Agent\.\.\.", "正在更新 Hermes Agent..."),
]


# 8. All 102 Slash Commands Descriptions
ZH_COMMAND_DESCRIPTIONS: dict[str, str] = {
    "start": "静默确认平台启动握手信号（无文本回复）",
    "new": "开启全新会话（生成新会话 ID 并清空上下文历史）",
    "topic": "启用或查看 Telegram 私聊多会话 Topics",
    "clear": "清屏并开启全新会话",
    "redraw": "强制重绘终端 UI 界面（修复终端输出漂移）",
    "history": "查看当前会话的完整历史对话记录",
    "save": "导出当前会话对话记录（支持 json/md/html 格式）",
    "retry": "重新发送上一条消息并重试代理回复",
    "prompt": "在外部编辑器 ($EDITOR) 中编写提示词并发送",
    "undo": "回退最近 N 轮用户对话并重新输入提示词",
    "title": "设置或修改当前会话的自定义标题",
    "handoff": "将会话交接转移至消息平台（Telegram、Discord 等）",
    "branch": "从当前会话派生新分支（探索不同的对话或任务路径）",
    "worktree": "查看、创建、列出或清理隔离的 Git Worktree 工作树",
    "compress": "主动压缩当前会话上下文（支持保留最近 N 轮）",
    "rollback": "查看或恢复文件系统自动快照检查点（保留手动编辑）",
    "snapshot": "创建或恢复 Hermes 配置与运行状态快照",
    "export": "将当前配置文件（配置、技能、主题）导出为分享压缩包",
    "import": "导入分享的配置压缩包作为新配置文件",
    "stop": "立即强制终止所有运行中的后台进程与当前任务",
    "pause": "全局紧急暂停所有新任务；输入 '/pause off' 恢复",
    "approve": "人工审批放行待处理的高风险终端命令",
    "deny": "拒绝执行待处理的高风险终端命令（可附加拒绝原因）",
    "bg": "在独立后台会话中运行提示词，不阻塞当前主对话",
    "btw": "就当前对话进行单次旁白侧问，不打断主任务且不存入历史",
    "agents": "查看当前正在运行的活跃代理与后台任务",
    "journey": "打开经验成长与学习历程时间线 (Journey)",
    "queue": "将提示词加入下轮执行队列，或管理排队任务列表",
    "steer": "在下一次工具调用后即时注入修正指令，无缝调整方向",
    "goal": "设定持久跨轮次目标，Hermes 将自动持续执行直到达成",
    "heartbeat": "设定会话心跳定时器，在空闲时自动重入执行",
    "refine": "复盘当前对话经验并提取沉淀到记忆库与技能中",
    "review": "委派独立子代理对刚才讨论的工作进行代码或文档评审",
    "loop": "在当前会话中按指定时间间隔循环执行提示词",
    "plan": "在 .hermes/plans/ 中生成 Markdown 实施计划（不执行任何操作）",
    "moa": "通过默认 Mixture-of-Agents (MoA) 预设运行单次提示词",
    "subgoal": "为当前活跃目标添加或管理子目标和额外验收条件",
    "status": "查看会话、模型、Token 消耗与上下文详细状态",
    "egress": "查看 Docker 外部网络出口代理状态",
    "context": "查看上下文窗口占用、分类明细、压缩统计与吞吐量",
    "whoami": "查看当前用户身份与可用斜杠指令权限（管理员/普通用户）",
    "profile": "查看当前正在生效的配置文件名称与主目录",
    "sethome": "将当前聊天频道设为主频道（Home Channel）",
    "resume": "恢复并继续之前已命名的历史会话",
    "sessions": "浏览、搜索并恢复历史会话记录",
    "config": "查看或检索当前生效的完整系统配置",
    "model": "切换当前会话模型（加 --global 可全局持久化保存）",
    "codex-runtime": "为 OpenAI/Codex 系列模型切换 Codex 运行时服务",
    "personality": "设置或切换预定义的人格预设",
    "statusbar": "切换底部上下文/模型状态栏显示开关",
    "battery": "切换状态栏中的电量与 Token 消耗颜色指示器",
    "timestamps": "切换消息与历史记录中的 [HH:MM] 时间戳显示",
    "diff": "查看当前工作目录中的 Git 文件修改差异",
    "verbose": "循环切换工具执行进度显示级别（off → new → all → verbose）",
    "focus": "切换专注模式 — 仅显示您的输入和最终回复结果",
    "footer": "切换最终回复底部的网关运行时元数据页脚显示",
    "yolo": "切换 YOLO 极速模式（本会话跳过所有高危命令人工审批）",
    "approvals": "查看或设置持久化高危命令审批模式",
    "reasoning": "管理模型深度思考/推理强度 (effort) 与显示开关",
    "fast": "极速处理模式 — 切换 Priority / Fast Mode 调度通道",
    "skin": "查看或切换终端与界面显示皮肤主题",
    "indicator": "选择终端 TUI 忙碌指示器动画样式",
    "voice": "切换或管理语音交互模式与 TTS 语音合成",
    "wake": "切换 'Hey Hermes' 语音唤醒监听功能",
    "busy": "配置 Hermes 正在处理任务时新消息的响应行为（排队/注入/打断）",
    "tools": "管理工具：查看、启用或禁用指定内置或扩展工具",
    "toolsets": "列出当前会话可用的工具集分组 (Toolsets)",
    "skills": "搜索、安装、检查或管理技能，以及审批暂存的技能修改",
    "memory": "审查待提交的记忆修改提案 / 切换记忆审批开关",
    "bundles": "管理技能捆绑包（通过 /<名称> 一键加载多个技能）",
    "pet": "切换或认养 Petdex 宠物助手 (/pet, /pet list, /pet <slug>)",
    "hatch": "根据自定义描述孵化并生成全新的 Petdex 宠物",
    "learn": "从指定目录、URL、当前对话或笔记中沉淀出可复用技能",
    "init": "基于代码仓库扫描自动生成或更新 AGENTS.md 指南",
    "cron": "管理后台定时计划任务 (Cron Jobs)",
    "suggestions": "查看并处理系统建议的自动化任务（接受/忽略）",
    "blueprint": "根据蓝图模板快速初始化并配置自动化任务",
    "curator": "后台技能维护与策展人（查看状态、运行分析、固定、归档）",
    "kanban": "多 Profile 跨渠道协同看板（任务、关联、评论与协作）",
    "reload": "将 .env 环境变量即时重载至当前运行会话",
    "reload-mcp": "从配置文件重新加载 MCP 外部扩展服务并刷新工具",
    "reload-skills": "重新扫描 ~/.hermes/skills/ 以同步新增或移除的技能",
    "browser": "将浏览器工具连接到活跃 Chromium 浏览器或切换 Browser Use 模式",
    "plugins": "列出已安装插件清单及其运行状态",
    "commands": "分页浏览所有可用系统指令与扩展技能",
    "help": "查看可用指令帮助列表（/help skills 查看技能，/help <关键词> 过滤）",
    "palette": "打开模糊搜索命令面板（亦可使用快捷键 Ctrl+P）",
    "restart": "安全优雅重启网关（平滑排空当前活跃任务后重启）",
    "usage": "查看 Token 消耗统计与限流配额状态",
    "subscription": "查看并在浏览器中管理您的 Nous 服务订阅计划",
    "login": "登录 Nous 官方账号（保留所有现有连接凭据）",
    "topup": "查看 Nous 账户余额并在门户进行充值与账单管理",
    "insights": "查看 Token 消耗深度分析与使用洞察图表",
    "platforms": "查看网关已连接的各即时通讯平台状态",
    "platform": "查看、暂停或恢复出现异常的网关平台适配器",
    "copy": "将助手上一条回复内容复制到系统剪贴板",
    "paste": "从系统剪贴板粘贴图片并附加到下一条提示词中",
    "image": "选择并附加本地图片文件到下一条提示词中",
    "update": "将 Hermes Agent 在线升级至官方最新版本",
    "version": "查看 Hermes Agent 当前运行版本信息",
    "debug": "导出并上传调试诊断报告（系统配置 + 运行时日志）",
    "quit": "退出 Hermes 交互式终端（加 --delete 可同步删除会话历史）",
}

# 9. Comprehensive i18n overlay dictionary for agent.i18n
ZH_I18N_OVERRIDES: dict[str, str] = {
    # Restart & Lifecycle
    "gateway.draining": "⏳ 正在等待 {count} 个活跃代理结束后重启...",
    "gateway.restart.in_progress": "⏳ 网关重启已在进行中...",
    "gateway.restart.restarting": "♻ 正在重启网关。如果 60 秒内没有收到通知，请在控制台运行 `hermes gateway restart` 重启。",
    # Status
    "gateway.status.header": "📊 **Hermes 网关状态**",
    "gateway.status.session_id": "**会话 ID：** `{session_id}`",
    "gateway.status.title": "**标题：** {title}",
    "gateway.status.created": "**创建时间：** {timestamp}",
    "gateway.status.last_activity": "**最近活动：** {timestamp}",
    "gateway.status.model": "**模型：** `{model}`",
    "gateway.status.model_provider": "**模型：** `{model}` ({provider})",
    "gateway.status.free_tier": "Nous · 免费套餐 · nous/welcome · /login 登录",
    "gateway.status.context": "**上下文：** {used} / {total} ({pct}%)",
    "gateway.status.context_used": "**上下文：** ~{used} Token",
    "gateway.status.tokens": "**累计计费 Token：** {tokens} _(非当前上下文占用；使用 `/context` 查看)_",
    "gateway.status.agent_running": "**代理运行中：** {state}",
    "gateway.status.state_yes": "是 ⚡",
    "gateway.status.state_no": "否",
    "gateway.status.queued": "**排队的后续：** {count}",
    "gateway.status.platforms": "**已连接平台：** {platforms}",
    "gateway.status.matrix_scope_header": "**Matrix 作用域：**",
    "gateway.status.matrix_scope_room": "  房间: {room}",
    "gateway.status.matrix_scope_room_id": "  房间 ID: {room_id}",
    "gateway.status.matrix_scope_thread": "  线程 ID: {thread_id}",
    "gateway.status.matrix_scope_mode": "  会话作用域: {scope}",
    "gateway.status.matrix_scope_key": "  会话标识: {session_key}",

    # Context
    "gateway.context.header": "🧠 **上下文窗口 (Context Window)**",
    "gateway.context.model": "模型：`{model}`",
    "gateway.context.window": "窗口总容量：{total} Token",
    "gateway.context.in_use": "当前占用：{used} / {total} ({pct}%)",
    "gateway.context.bar": "{bar}",
    "gateway.context.headroom": "距上限余量：{headroom} Token",
    "gateway.context.threshold": "自动压缩阈值：{threshold} ({threshold_pct}%) — 剩余 {to_go} Token 触发",
    "gateway.context.over_threshold": "⚠️ **已超过自动压缩阈值 ({threshold}, {threshold_pct}%)**",
    "gateway.context.compressions": "本会话压缩次数：{count}",
    "gateway.context.last_savings": "上次压缩释放空间：{savings}%",
    "gateway.context.totals_header": "会话累计总计 (跨 {calls} 次 API 调用)",
    "gateway.context.totals_line": "输入 {input} · 输出 {output} · 思考 {reasoning}",
    "gateway.context.total_billed": "累计计费：{total} Token",
    "gateway.context.throughput_note": "_此为吞吐总量，非当前上下文大小 — 每次调用均需重新传递上方窗口。_",
    "gateway.context.estimated": "预估上下文：~{count} Token，跨 {messages} 条消息",
    "gateway.context.detail_after_first": "_(完整的压缩与吞吐统计将在模型首次回复后可用)_",
    "gateway.context.no_data": "暂无可用上下文数据。发送一条消息以开启会话。",

    # Resume
    "gateway.resume.db_unavailable": "会话数据库不可用。",
    "gateway.resume.parse_error": "⚠️ 无法解析 `/resume` 参数：{error}。\n对于包含空格的会话标题请使用引号包裹，例如：`/resume \"项目 A 计划\"`。",
    "gateway.resume.matrix_no_named_sessions": "未找到当前 Matrix 房间的已命名会话。\n使用 `/title 我的会话` 命名当前会话，使用 `/resume --all` 列出全部会话，或使用 `/resume --cross-room <会话名称>` 明确跨房间恢复。",
    "gateway.resume.matrix_blocked_no_origin": "⚠️ Matrix /resume 已拦截：该指定会话未记录房间归属，Hermes 默认不会在当前房间恢复。若确需跨房间恢复，请使用 `/resume --cross-room {name}`。",
    "gateway.resume.matrix_blocked_other_room": "⚠️ Matrix /resume 已拦截：该会话属于其他 Matrix 房间 ({room})。若确需恢复至此处，请使用 `/resume --cross-room {name}`。",
    "gateway.resume.matrix_cross_room_success": "⚠️ 跨房间恢复：已在 Matrix 房间 **{room}** 中恢复 **{title}**。\n本房间的后续消息将使用该历史记录，直到 `/reset` 或再次执行 `/resume`。{msg_part}",
    "gateway.resume.blocked_not_owner": "⚠️ /resume 已拦截：'**{name}**' 属于其他用户或聊天。您只能恢复来自本聊天的会话。",
    "gateway.resume.no_named_sessions": "未找到已命名的会话。\n使用 `/title 我的会话` 为当前会话命名，然后用 `/resume 我的会话` 返回。",
    "gateway.resume.all_requires_admin": "_注意：`--all`（跨聊天列表）需要已配置的管理员；仅显示本聊天的会话。_",
    "gateway.resume.list_header": "📋 **已命名会话**\n",
    "gateway.resume.list_item": "• **{title}**{preview_part}",
    "gateway.resume.list_item_numbered": "{index}. **{title}**{preview_part}",
    "gateway.resume.list_preview_suffix": " — _{preview}_",
    "gateway.resume.list_footer": "\n用法：`/resume <会话名称>`",
    "gateway.resume.list_footer_numbered": "\n用法：`/resume <会话名称>` 或 `/resume <编号>`（例如，`/resume 1` 表示最近的会话）",
    "gateway.resume.list_failed": "无法列出会话：{error}",
    "gateway.resume.out_of_range": "恢复索引 {index} 超出范围。\n请使用不带参数的 `/resume` 查看可用会话。",
    "gateway.resume.not_found": "未找到匹配 '**{name}**' 的会话。\n使用不带参数的 `/resume` 查看可用会话。",
    "gateway.resume.already_on": "📌 已在会话 **{name}** 上。",
    "gateway.resume.switch_failed": "切换会话失败。",
    "gateway.resume.resumed_one": "↻ 已恢复会话 **{title}**（{count} 条消息）。对话已还原。",
    "gateway.resume.resumed_many": "↻ 已恢复会话 **{title}**（{count} 条消息）。对话已还原。",
    "gateway.resume.resumed_no_count": "↻ 已恢复会话 **{title}**。对话已还原。",

    # Fast
    "gateway.fast.not_supported": "⚡ /fast 仅适用于支持优先处理（Priority Processing）的 OpenAI 模型。",
    "gateway.fast.status": "⚡ 优先处理\n\n当前模式：`{mode}`\n\n_用法：_ `/fast <normal|fast|status>`",
    "gateway.fast.unknown_arg": "⚠️ 未知参数：`{arg}`\n\n**有效选项：** normal、fast、status",
    "gateway.fast.saved": "⚡ ✓ 优先处理：**{label}**（已保存到配置）\n_（下一条消息生效）_",
    "gateway.fast.session_only": "⚡ ✓ 优先处理：**{label}**（仅本次会话）",
    "gateway.fast.label_fast": "极速 (FAST)",
    "gateway.fast.label_normal": "标准 (NORMAL)",
    "gateway.fast.status_fast": "极速模式 (fast)",
    "gateway.fast.status_normal": "标准模式 (normal)",
    "gateway.fast.picker_title": "⚡ **优先处理**\n\n当前模式：`{mode}`\n\n请选择：",
    "gateway.fast.choice_fast": "fast — 开启优先处理",
    "gateway.fast.choice_normal": "normal — 标准处理",
    "gateway.fast.choice_auto": "auto — 每轮的前几秒快速",
    "gateway.fast.choice_cold": "cold — 仅会话的第一轮快速",

    # Reasoning
    "gateway.reasoning.level_default": "medium（默认）",
    "gateway.reasoning.level_disabled": "none（已禁用）",
    "gateway.reasoning.scope_session": "会话覆盖",
    "gateway.reasoning.scope_global": "全局配置",
    "gateway.reasoning.status": "🧠 **推理设置**\n\n**强度：** `{level}`\n**作用域：** {scope}\n**显示：** {display}\n\n_用法：_ `/reasoning <none|minimal|low|medium|high|xhigh|max|ultra|reset|show|hide> [--global]`",
    "gateway.reasoning.display_on": "开 ✓",
    "gateway.reasoning.display_off": "关",
    "gateway.reasoning.display_set_on": "🧠 ✓ 推理显示：**开启**\n在 **{platform}** 上每次响应前将显示模型的思考过程。",
    "gateway.reasoning.display_set_off": "🧠 ✓ **{platform}** 上的推理显示：**关闭**",
    "gateway.reasoning.display_saved": "🧠 ✓ 推理显示：**{state}**（已保存到配置）\n_（下一条消息生效）_",
    "gateway.reasoning.display_session_only": "🧠 ✓ 推理显示：**{state}**（仅本会话）",
    "gateway.reasoning.reset_global_unsupported": "⚠️ 不支持 `/reasoning reset --global`。请使用 `/reasoning <level> --global` 修改全局默认值。",
    "gateway.reasoning.reset_done": "🧠 ✓ 已清除本会话的推理覆盖；回退到全局配置。",
    "gateway.reasoning.reset_none": "🧠 当前没有活动的推理强度覆盖。",
    "gateway.reasoning.unknown_arg": "⚠️ 未知参数：`{arg}`\n\n**有效级别：** none, minimal, low, medium, high, xhigh, max, ultra\n**显示：** show, hide\n**持久化：** 添加 `--global` 以跨会话保存",
    "gateway.reasoning.picker_title": "🧠 **推理设置**\n\n**强度：** `{level}`\n**作用域：** {scope}\n**显示：** {display}\n\n请选择：",
    "gateway.reasoning.choice_none": "none — 关闭推理",
    "gateway.reasoning.choice_reset": "reset — 清除会话覆盖",
    "gateway.reasoning.choice_show": "在回复中显示推理",
    "gateway.reasoning.choice_hide": "在回复中隐藏推理",
    "gateway.reasoning.set_global": "🧠 ✓ 推理强度已设置为 `{effort}`（已保存到配置）\n_（下一条消息生效）_",
    "gateway.reasoning.set_global_save_failed": "🧠 ✓ 推理强度已设置为 `{effort}`（仅本会话 — 配置保存失败）\n_（下一条消息生效）_",
    "gateway.reasoning.set_session": "🧠 ✓ 推理强度已设置为 `{effort}`（仅本会话 — 添加 `--global` 以持久化）\n_（下一条消息生效）_",

    # Model
    "gateway.model.context_label": "上下文",
    "gateway.model.max_output_label": "最大输出",
    "gateway.model.capabilities_label": "模型特性",
    "gateway.model.provider_label": "提供商",

    # Commands & Help
    "gateway.help.header": "📖 **Hermes 命令指南**\n",
    "gateway.help.skill_header": "\n⚡ **扩展技能指令**（{count} 个活跃）：",
    "gateway.help.more_use_commands": "\n... 还有 {count} 个。输入 `/commands` 查看完整分页列表。",
    "gateway.commands.usage": "用法：`/commands [页码]`",
    "gateway.commands.skill_header": "⚡ **扩展技能指令**：",
    "gateway.commands.default_desc": "扩展技能指令",
    "gateway.commands.none": "当前没有可用的指令。",
    "gateway.commands.header": "📚 **指令大全**（共 {total} 个，第 {page}/{total_pages} 页）",
    "gateway.commands.nav_prev": "`/commands {page}` ← 上一页",
    "gateway.commands.nav_next": "下一页 → `/commands {page}`",
    "gateway.commands.out_of_range": "_（请求的第 {requested} 页超出范围，已显示第 {page} 页。）_",

    # Usage
    "gateway.usage.rate_limits": "⏱️ **速率限制：** {state}",
    "gateway.usage.header_session": "📊 **会话 Token 使用统计**",
    "gateway.usage.label_model": "模型：`{model}`",
    "gateway.usage.label_input_tokens": "输入 Token：{count}",
    "gateway.usage.label_cache_read": "缓存读取 Token：{count}",
    "gateway.usage.label_cache_write": "缓存写入 Token：{count}",
    "gateway.usage.label_output_tokens": "输出 Token：{count}",
    "gateway.usage.label_total": "总计：{count}",
    "gateway.usage.label_api_calls": "API 调用次数：{count}",
    "gateway.usage.label_cost": "费用：{prefix}${amount}",
    "gateway.usage.label_cost_included": "费用：已包含",
    "gateway.usage.label_context": "上下文：{used} / {total}（{pct}%）",
    "gateway.usage.label_compressions": "压缩次数：{count}",
    "gateway.usage.breakdown_header": "🧩 **按分类预估占用明细**",
    "gateway.usage.breakdown_line": "• {label}：约 {count} ({pct}%)",
    "gateway.usage.breakdown_cat_system_prompt": "系统提示词",
    "gateway.usage.breakdown_cat_tool_definitions": "工具定义",
    "gateway.usage.breakdown_cat_rules": "规则指令",
    "gateway.usage.breakdown_cat_skills": "技能",
    "gateway.usage.breakdown_cat_mcp": "MCP 工具",
    "gateway.usage.breakdown_cat_subagent_definitions": "子代理定义",
    "gateway.usage.breakdown_cat_memory": "记忆",
    "gateway.usage.breakdown_cat_conversation": "对话历史",
    "gateway.usage.header_session_info": "📊 **会话信息**",
    "gateway.usage.label_messages": "消息数：{count}",
    "gateway.usage.label_estimated_context": "预估上下文：~{count} Token",
    "gateway.usage.detailed_after_first": "_（首次代理响应后可查看详细使用统计）_",
    "gateway.usage.no_data": "此会话暂无使用数据。",
    "gateway.usage.unknown_subcommand": "未知的 /usage 子命令：`{args}`。请尝试 `/usage` 或 `/usage reset [--force]`。",
    "gateway.usage.reset_wrong_provider": "存储的用量重置仅在 openai-codex 提供商上可用。请先使用 `/model` 切换。",
}

# Eagerly sanitize all static override entries against accidental literal newlines
for _k, _v in list(ZH_I18N_OVERRIDES.items()):
    if isinstance(_v, str) and r"\n" in _v:
        ZH_I18N_OVERRIDES[_k] = sanitize_literal_newlines(_v)

for _k, _v in list(ZH_COMMAND_DESCRIPTIONS.items()):
    if isinstance(_v, str) and r"\n" in _v:
        ZH_COMMAND_DESCRIPTIONS[_k] = sanitize_literal_newlines(_v)

_ZH_TIPS_MAP: dict[str, str] = {}
_ZH_TIPS_LIST: list[str] = []


def _load_tips_data() -> bool:
    """Load Chinese tips data into module cache."""
    global _ZH_TIPS_MAP, _ZH_TIPS_LIST
    if _ZH_TIPS_MAP:
        return True
    candidates = [
        Path(__file__).resolve().parent / "tips_zh.json",
        Path.home() / ".hermes" / "plugins" / "hermes-zh" / "tips_zh.json",
    ]
    for p in candidates:
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                _ZH_TIPS_LIST = data.get("tips") if isinstance(data, dict) else (data if isinstance(data, list) else [])
                _ZH_TIPS_MAP = data.get("map") if isinstance(data, dict) else {}
                return True
            except Exception as exc:
                logger.debug("Failed loading tips from %s: %s", p, exc)
    return False

# 9.1 Model & Provider Failover / Fallback Reason Mapping and Interceptor
ZH_FALLBACK_REASONS: dict[str, str] = {
    # FailoverReason enum labels
    "request timeout": "请求超时",
    "timeout": "请求超时",
    "rate limit": "触发速率限制",
    "rate_limit": "触发速率限制",
    "upstream model rate limit": "上游模型请求频次受限",
    "billing or quota exhausted": "额度或余额耗尽",
    "provider overloaded": "服务商过载",
    "overloaded": "服务商过载",
    "provider server error": "服务商服务器错误",
    "server error": "服务器错误",
    "server_error": "服务器错误",
    "authentication failed": "身份鉴权失败",
    "authentication permanently failed": "身份鉴权永久失败",
    "auth failed": "身份鉴权失败",
    "tls certificate verification failed": "TLS 证书校验失败",
    "ssl certificate verification failed": "SSL 证书校验失败",
    "context window exceeded": "超出上下文窗口容量",
    "context overflow": "超出上下文窗口容量",
    "request payload too large": "请求载荷过大",
    "payload too large": "请求载荷过大",
    "image payload too large": "图片载荷过大",
    "image too large": "图片载荷过大",
    "model not found": "模型不存在",
    "provider policy blocked the request": "服务商策略拦截该请求",
    "provider policy blocked": "服务商策略拦截该请求",
    "content policy blocked the request": "内容安全策略拦截该请求",
    "content policy blocked": "内容安全策略拦截该请求",
    "request format rejected": "请求格式被拒绝",
    "format error": "请求格式被拒绝",
    "adjacent same-role messages rejected": "相邻同角色消息被拒绝",
    "role alternation": "相邻同角色消息被拒绝",
    "encrypted reasoning state rejected": "加密思考状态被拒绝",
    "invalid encrypted content": "加密思考状态被拒绝",
    "multimodal tool content unsupported": "不支持多模态工具内容",
    "thinking signature rejected": "思考签名被拒绝",
    "thinking signature": "思考签名被拒绝",
    "long-context tier unavailable": "长上下文服务层不可用",
    "oauth long-context beta unavailable": "OAuth 长上下文测试版不可用",
    "grammar pattern rejected": "语法模式被拒绝",
    "provider failure": "服务商故障",

    # Common network / API errors
    "connection lost": "网络连接中断",
    "connection reset": "网络连接重置",
    "connection closed": "网络连接关闭",
    "connection terminated": "网络连接终止",
    "network error": "网络错误",
    "upstream connect error": "上游连接错误",
    "peer closed": "对端关闭连接",
    "broken pipe": "管道断开",
    "bad gateway": "网关错误",
    "gateway timeout": "网关超时",
    "service unavailable": "服务暂时不可用",
    "internal server error": "内部服务器错误",
    "model cooldown": "模型处于冷却状态",
    "model unavailable": "模型不可用",
    "provider unavailable": "服务商不可用",
    "fallback candidate unavailable": "备用模型候选不可用",
    "capacity exhausted": "算力容量耗尽",
}


def translate_fallback_reason(reason: str) -> str:
    """Translate model failover reason to concise Chinese."""
    if not reason:
        return "未知原因"
    clean = reason.strip().strip("()")
    lower = clean.lower()
    if lower in ZH_FALLBACK_REASONS:
        return ZH_FALLBACK_REASONS[lower]
    normalized = lower.replace("_", " ")
    if normalized in ZH_FALLBACK_REASONS:
        return ZH_FALLBACK_REASONS[normalized]
    for en_key, zh_val in ZH_FALLBACK_REASONS.items():
        if en_key in normalized:
            return zh_val
    return clean


def _format_fallback_target(target: str) -> str:
    target = target.strip()
    m = re.match(r"^(.+?)\s+via\s+(\S+)$", target, re.IGNORECASE)
    if m:
        model, provider = m.group(1), m.group(2)
        return f"{model}（通过 {provider}）"
    return target


_MODEL_FALLBACK_RE = re.compile(
    r"(?i)(?P<emoji>⚠️\s*)?\*?\*?model fallback\*?\*?:\s*"
    r"(?P<old_target>.+?)\s+unavailable\s*\((?P<reason>[^)]+)\);\s*"
    r"using\s+(?P<fb_target>[^\r\n]+?)\."
    r"(?=\s+Primary retry|\s*$|\n)"
    r"(?P<retry>\s*Primary retry eligible in ~?(?P<remaining>\d+)\s*s;\s*recovery is not guaranteed\.?)?"
)


def _replace_model_fallback(m: re.Match) -> str:
    old_target = _format_fallback_target(m.group("old_target"))
    reason_zh = translate_fallback_reason(m.group("reason"))
    fb_target = _format_fallback_target(m.group("fb_target"))
    remaining = m.group("remaining")
    retry_zh = f" 预计约 {remaining} 秒后可重试主模型（不保证恢复）。" if remaining else ""
    sep = "" if old_target.endswith("）") else " "
    return f"⚠️ 模型故障回退：{old_target}{sep}不可用（{reason_zh}）；已改用 {fb_target}。{retry_zh}".rstrip()


_PROVIDER_FALLBACK_RE = re.compile(
    r"(?i)(?P<emoji>⚠️\s*)?\*?\*?provider fallback\*?\*?:\s*(?P<primary>[^\r\n;]+?)\s+unavailable;\s*using\s+(?P<fallback>[^\r\n.]+?)\s+for this response\.?"
)


def _replace_provider_fallback(m: re.Match) -> str:
    primary = m.group("primary").strip()
    fallback = m.group("fallback").strip()
    return f"⚠️ 服务商故障回退：{primary} 不可用；本次响应改用 {fallback}。"


_EXTRA_FALLBACK_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"🔄\s*Primary model failed — switching to fallback:\s*(.+)", re.IGNORECASE), r"🔄 主模型调用失败 — 正在切换至备用模型：\1"),
    (re.compile(r"🔄\s*Switched to fallback model:\s*(.+)", re.IGNORECASE), r"🔄 已切换至备用模型：\1"),
    (re.compile(r"↻\s*Switched to fallback:\s*(.+)", re.IGNORECASE), r"↻ 已切换至备用模型：\1"),
]


def translate_fallback_notice(content: str) -> str:
    """Translate model and provider fallback notices into idiomatic Chinese."""
    if not isinstance(content, str) or not content:
        return content
    res = content
    if re.search(r"(?i)model fallback", res):
        res = _MODEL_FALLBACK_RE.sub(_replace_model_fallback, res)
    if re.search(r"(?i)provider fallback", res):
        res = _PROVIDER_FALLBACK_RE.sub(_replace_provider_fallback, res)
    for pat, rep in _EXTRA_FALLBACK_PATTERNS:
        if pat.search(res):
            res = pat.sub(rep, res)
    return res


def translate_telegram_content(content: str) -> str:
    """Translate non-conversational system notices passing through Telegram adapter."""
    if not isinstance(content, str):
        return content
    content = sanitize_literal_newlines(content)
    content = translate_fallback_notice(content)
    # 0. Lifecycle & System Notices (gateway restart, shutdown, update, online, db warnings)
    for pat, rep in SYSTEM_NOTICES_PATTERNS:
        if re.search(pat, content):
            content = re.sub(pat, rep, content)


    # 1. Background review summary
    m_rev = re.match(r"^\s*💾\s*Self-improvement review:\s*(.*)$", content, re.IGNORECASE)
    if m_rev:
        sub = translate_review_summary(m_rev.group(1).strip())
        return f"💾 自我提升复盘：{sub}"

    # 2. Heartbeat: ⏳ Working — 9 min — iteration 62/500, waiting for provider response (streaming)
    m_hb = re.match(r"^\s*⏳\s*Working\s*—\s*(\d+)\s*min(.*)$", content, re.IGNORECASE)
    if m_hb:
        mins = m_hb.group(1)
        detail = m_hb.group(2)
        detail = re.sub(r"\biteration\s+(\d+)/(\d+)\b", r"轮次 \1/\2", detail, flags=re.IGNORECASE)
        detail = re.sub(r"\biteration\s+(\d+)\b", r"轮次 \1", detail, flags=re.IGNORECASE)
        detail = detail.replace("waiting for provider response (streaming)", "等待模型响应 (流式)")
        detail = detail.replace("waiting for provider response", "等待模型响应")
        for tname, tverb in ZH_TOOL_VERBS.items():
            detail = re.sub(rf"\bexecuting tool:\s*{tname}\b", f"正在执行: {tverb}", detail)
            detail = re.sub(rf"\brunning:\s*{tname}\b", f"正在运行: {tverb}", detail)
            detail = re.sub(rf"(?<=—\s){tname}(?=\s*$|,)", tverb, detail)
        detail = detail.replace(", ", "，")
        return f"⏳ 正在处理中 — {mins} 分钟{detail}"

    # 3. Approval resolution in messages
    if any(k in content for k in ("Approved for session by", "Approved once by", "Approved permanently by", "Denied by", "Approval expired")):
        return translate_approval_resolution(content)

    # 4. Busy ack notices
    for h_en, h_zh in BUSY_HEAD_MAP.items():
        if content.startswith(h_en):
            res = content.replace(h_en, h_zh, 1)
            for t_en, t_zh in BUSY_TAIL_MAP.items():
                if res.endswith(t_en):
                    res = res[:-len(t_en)] + t_zh
            return res

    # 5. Session Info block (reset card, /new, auto-reset)
    if "◆ Model:" in content or "◆ Provider:" in content or "◐ Session reset" in content:
        res = content
        for pat, rep in AUTO_RESET_PATTERNS:
            res = re.sub(pat, rep, res)
        for pat, rep in SESSION_INFO_MAP:
            res = re.sub(pat, rep, res)

        m_tip = re.search(r"(✦\s*(?:提示|Tip)[：:]\s*)(.*)$", res, re.DOTALL)
        if m_tip:
            raw_tip = m_tip.group(2).strip()
            _load_tips_data()
            if raw_tip in _ZH_TIPS_MAP:
                res = res[:m_tip.start(2)] + _ZH_TIPS_MAP[raw_tip]

        return res

    # 6. Status command output (safety net)
    if "Hermes 网关状态" in content or "Gateway platforms" in content or "Lifetime tokens billed" in content:
        res = content
        res = re.sub(r"\bModel:\s*", "模型：", res)
        res = re.sub(r"\*\*Model:\*\*\s*", "**模型：** ", res)
        res = re.sub(r"\bContext:\s*", "上下文：", res)
        res = re.sub(r"\*\*Context:\*\*\s*", "**上下文：** ", res)
        res = re.sub(r"\bLifetime tokens billed:\s*", "累计计费 Token：", res)
        res = re.sub(r"\*\*Lifetime tokens billed:\*\*\s*", "**累计计费 Token：** ", res)
        res = re.sub(r"_\(not your current context size; use `/context`\)_", "_(非当前上下文占用；使用 `/context` 查看)_", res)
        res = re.sub(r"_\(not your current context size; use /context\)_", "_(非当前上下文占用；使用 /context 查看)_", res)
        res = re.sub(r"\(not your current context size; use /context\)", "(非当前上下文占用；使用 /context 查看)", res)
        res = re.sub(r"\bAgent running:\s*No\b", "代理运行中： 否", res)
        res = re.sub(r"\bAgent running:\s*Yes\b", "代理运行中： 是 ⚡", res)
        res = re.sub(r"\*\*Agent running:\*\*\s*No\b", "**代理运行中：** 否", res)
        res = re.sub(r"\*\*Agent running:\*\*\s*Yes\b", "**代理运行中：** 是 ⚡", res)
        res = re.sub(r"\bQueued follow-ups:\s*", "排队的后续任务: ", res)
        res = re.sub(r"\*\*Queued follow-ups:\*\*\s*", "**排队的后续：** ", res)

        def _format_platforms(m):
            prefix = m.group(1)
            raw_p = m.group(2)
            p_map = {"telegram": "Telegram", "webhook": "Webhook", "discord": "Discord", "slack": "Slack", "matrix": "Matrix"}
            parts = [p_map.get(p.strip().lower(), p.strip().title()) for p in raw_p.split(",")]
            return f"{prefix}{', '.join(parts)}"

        res = re.sub(r"((?:已连接平台|Connected platforms)[：:]\s*)([a-zA-Z0-9_,\s]+)", _format_platforms, res)
        res = res.replace("**Gateway platforms**", "**网关平台状态**")
        res = res.replace("Failed/paused: (none)", "失败/暂停: (无)")
        res = res.replace("Connected:", "已连接:")
        return res

    # 7. Context window command output (safety net)
    if any(k in content for k in (
        "Context Window",
        "Auto-compresses at:",
        "Estimated usage by category",
        "Context window:",
        "Toolsets by schema cost",
        "Skills by cost",
        "category counts are local estimates",
    )):
        res = content
        res = res.replace("🧠 **Context Window**", "🧠 **上下文窗口 (Context Window)**")
        res = res.replace("🧠 Context Window", "🧠 上下文窗口 (Context Window)")
        res = re.sub(r"^Model:\s*", "模型：", res, flags=re.M)
        res = re.sub(r"^Window:\s*(\d[0-9,]*)\s*tokens", r"窗口总容量：\1 Token", res, flags=re.M)
        res = re.sub(r"^In use:\s*", "当前占用：", res, flags=re.M)
        res = re.sub(r"^Headroom to limit:\s*(\d[0-9,]*)\s*tokens", r"距上限余量：\1 Token", res, flags=re.M)
        res = re.sub(r"^Auto-compresses at:\s*([^\n]+?)\s*—\s*([^\n]+?)\s*to go", r"自动压缩阈值：\1 — 剩余 \2 触发", res, flags=re.M)
        res = re.sub(r"^Compressions this session:\s*", "本会话压缩次数：", res, flags=re.M)
        res = re.sub(r"^Last compression freed:\s*([^\n]+?)\s*of context", r"上次压缩释放空间：\1 上下文", res, flags=re.M)
        res = re.sub(r"^Session totals \(cumulative across (\d+) API calls\)", r"会话累计总计 (跨 \1 次 API 调用)", res, flags=re.M)
        res = res.replace("Input ", "输入 ").replace(" · Output ", " · 输出 ").replace(" · Reasoning ", " · 思考 ")
        res = re.sub(r"^Total billed:\s*([0-9,]+)", r"累计计费：\1 Token", res, flags=re.M)
        res = res.replace("_Throughput, not context size — each call re-sends the window above._",
                          "_此为吞吐总量，非当前上下文大小 — 每次调用均需重新传递上方窗口。_")
        res = re.sub(r"^Estimated context:\s*~?([0-9,]+)\s*tokens across (\d+) messages",
                     r"预估上下文：~\1 Token，跨 \2 条消息", res, flags=re.M)
        res = res.replace("_(Full compression and throughput stats available after the first agent response)_",
                          "_(完整的压缩与吞吐统计将在模型首次回复后可用)_")
        res = res.replace("No context data available yet. Send a message to start a session.",
                          "暂无可用上下文数据。发送一条消息以开启会话。")

        # Breakdown table replacements
        res = res.replace("Estimated usage by category", "按分类预估占用明细")
        res = res.replace("(no data yet — send a message first)", "(暂无数据 — 请先发送一条消息)")
        res = res.replace("System prompt", "系统提示词")
        res = res.replace("Tool definitions", "工具定义")
        res = res.replace("Subagent definitions", "子代理定义")
        res = res.replace("Memory", "记忆")
        res = res.replace("Conversation", "对话历史")
        res = res.replace("Free space", "剩余空间")
        res = res.replace("Rules", "规则指令")
        res = res.replace("Skills", "技能")
        res = res.replace("MCP", "MCP 工具")

        # Details table replacements
        res = res.replace("Toolsets by schema cost (largest first)", "工具集按 Schema 开销排序（由大到小）")
        res = res.replace("Skills by cost (index = always-on; SKILL.md = cost when loaded)", "技能按开销排序（索引 = 常驻；SKILL.md = 加载时开销）")
        res = re.sub(r"\b(\d+)\s+tools\b", r"\1 个工具", res)
        res = re.sub(r"\bindex\s+~", "索引 ~", res)
        res = re.sub(r"… and (\d+) more", r"… 以及另外 \1 项", res)

        # Context window footer replacements
        res = re.sub(r"^Context window:\s*", "上下文窗口：", res, flags=re.M)
        res = re.sub(
            r"^Source:\s*(.*?);\s*category counts are local estimates\.",
            r"数据来源：\1；分类统计为本地预估。",
            res,
            flags=re.M,
        )
        res = re.sub(r"\bprovider usage \+ estimated new messages\b", "模型提供商实际用量 + 新消息预估", res)
        res = re.sub(r"\bprovider usage\b", "模型提供商实际用量", res)
        res = re.sub(r"\blocal estimate\b", "本地预估", res)
        res = res.replace(
            "Use /context all for per-skill and per-toolset costs.",
            "使用 /context all 查看各技能与工具集的明细开销。",
        )
        res = re.sub(r"\btokens\b", "Token", res)
        return res

    # 8. Identity & Slash permission notices (/whoami)
    if "**You** —" in content or "Slash commands you can run:" in content:
        res = content
        res = re.sub(r"\*\*You\*\*\s*—\s*(\S+)\s*\(([^)]+)\)", r"**当前身份** — \1 (\2)", res)
        res = res.replace("User ID:", "用户 ID:")
        res = res.replace("Tier: unrestricted (no admin list configured for this scope)", "权限级别: 无限制 (未配置管理员列表)")
        res = res.replace("Tier: **admin**", "权限级别: **管理员 (admin)**")
        res = res.replace("Tier: user", "权限级别: 普通用户 (user)")
        res = res.replace("Slash commands you can run:", "您可执行的斜杠指令:")
        res = res.replace("Slash commands: all available", "可用斜杠指令: 全部可用")
        return res

    # 9. Busy mode settings (/busy)
    if "Busy input mode:" in content or "Messages while busy:" in content:
        res = content
        res = res.replace("**Busy input mode:", "**忙碌输入模式：")
        res = res.replace("Messages while busy:", "忙碌期间行为:")
        res = res.replace("Change with", "切换方式:")
        res = res.replace("queues for next turn", "排队等待下轮执行")
        res = res.replace("steers into current run (after next tool call)", "在下次工具调用后注入当前任务")
        res = res.replace("interrupts current run", "立即中断当前任务")
        return res

    # 10. Progress lines (e.g. 🧠 memory... -> 🧠 正在更新记忆...)
    lines = content.split("\n")
    changed = False
    new_lines = []
    for line in lines:
        m_tool = re.match(r"^(\S+)\s+([a-zA-Z0-9_-]+)\.\.\.$", line.strip())
        if m_tool:
            emoji, tool_name = m_tool.group(1), m_tool.group(2)
            if tool_name in ZH_TOOL_VERBS:
                new_lines.append(f"{emoji} {ZH_TOOL_VERBS[tool_name]}...")
                changed = True
                continue
        new_lines.append(line)
    if changed:
        return "\n".join(new_lines)

    return content


# 11. Chinese preview builders for memory & tasks
def _zh_preview_memory(args: dict, max_len: int) -> str:
    """Smart Chinese preview for memory tool, supporting single action & batch operations."""
    try:
        import agent.display as display
        clip_fn, oneline_fn = display._clip, display._oneline
    except Exception:
        clip_fn = lambda s, n: s[:n] + ("..." if len(s) > n else "")
        oneline_fn = lambda s: " ".join(str(s).split())

    target = args.get("target", "")
    target_zh = "用户画像" if target == "user" else ("记忆库" if target == "memory" else (target or "记忆"))
    operations = args.get("operations")
    if operations and isinstance(operations, list):
        if len(operations) == 1 and isinstance(operations[0], dict):
            op = operations[0]
            op_act = op.get("action", "")
            if op_act == "add":
                cnt = op.get("content") or op.get("new_text") or ""
                return f"+{target_zh}: \"{clip_fn(oneline_fn(cnt), 25)}\""
            elif op_act in ("replace", "remove"):
                old = oneline_fn(op.get("old_text") or "") or "<待匹配文本>"
                prefix = "~" if op_act == "replace" else "-"
                return f"{prefix}{target_zh}: \"{old[:20]}\""
            return f"{target_zh} ({op_act})"
        return f"{target_zh} ({len(operations)} 项变更)"

    action = args.get("action", "")
    if action == "add":
        cnt = args.get("content") or args.get("new_text") or ""
        return f"+{target_zh}: \"{clip_fn(oneline_fn(cnt), 25)}\""
    if action in ("replace", "remove"):
        old = oneline_fn(args.get("old_text") or "") or "<待匹配文本>"
        prefix = "~" if action == "replace" else "-"
        return f"{prefix}{target_zh}: \"{old[:20]}\""

    return target_zh


def _zh_preview_todo_list(args: dict, _max_len: int) -> str:
    """Chinese preview for todo_list tool."""
    todos_arg = args.get("todos")
    verb = "更新" if args.get("merge", False) else "规划"
    return "读取待办清单" if todos_arg is None else f"{verb} {len(todos_arg)} 个任务"


def patch_display() -> bool:
    """Safely update agent.display tool verbs and custom preview builders."""
    try:
        import agent.display as display
        display._TOOL_VERBS.update(ZH_TOOL_VERBS)
        if hasattr(display, "_PREVIEW_BUILDERS"):
            display._PREVIEW_BUILDERS["memory"] = _zh_preview_memory
            display._PREVIEW_BUILDERS["todo_list"] = _zh_preview_todo_list
            if "session_search" in display._PREVIEW_BUILDERS:
                display._PREVIEW_BUILDERS["session_search"] = (
                    lambda args, _m: f"检索: \"{display._clip(display._oneline(args.get('query', '')), 25)}\""
                )
        return True
    except Exception as exc:
        logger.debug("patch_display failed: %s", exc)
        return False


def patch_activity() -> bool:
    """Safely patch format_iteration_progress to output Chinese."""
    try:
        import agent.session_activity as sa
        if getattr(sa, "_hermes_zh_activity_patched", False):
            return True

        def _zh_format_iteration_progress(api_call_count: Any, max_iterations: Any) -> str:
            try:
                cap = int(max_iterations)
            except (TypeError, ValueError):
                cap = sys.maxsize
            if cap >= sys.maxsize:
                return f"轮次 {api_call_count}"
            return f"轮次 {api_call_count}/{cap}"

        sa.format_iteration_progress = _zh_format_iteration_progress
        sa._hermes_zh_activity_patched = True

        if "gateway.run_turn" in sys.modules:
            sys.modules["gateway.run_turn"].format_iteration_progress = _zh_format_iteration_progress
        if "gateway.run_busy" in sys.modules:
            sys.modules["gateway.run_busy"].format_iteration_progress = _zh_format_iteration_progress

        return True
    except Exception as exc:
        logger.debug("patch_activity failed: %s", exc)
        return False


def patch_background_review() -> bool:
    """Safely patch agent.background_review._publish_review_summary to output Chinese."""
    try:
        import agent.background_review as br
        if getattr(br, "_hermes_zh_review_patched", False):
            return True

        orig_publish = br._publish_review_summary

        def _zh_publish_review_summary(agent: Any, actions: list[str]) -> None:
            zh_actions = [translate_review_summary(a) for a in actions]
            summary = " · ".join(dict.fromkeys(zh_actions))
            agent._safe_print(f"  💾 自我提升复盘：{summary}")
            if agent.background_review_callback:
                with suppress(Exception):
                    agent.background_review_callback(f"💾 自我提升复盘：{summary}")

        br._publish_review_summary = _zh_publish_review_summary
        br._hermes_zh_review_patched = True
        return True
    except Exception as exc:
        logger.debug("patch_background_review failed: %s", exc)
        return False


def patch_runner() -> bool:
    """Safely patch TurnRunner._progress_build_message to catch unlocalized tool names."""
    try:
        from gateway.run_turn_runner import TurnRunner
        if getattr(TurnRunner, "_hermes_zh_runner_patched", False):
            return True

        orig_progress_build_message = TurnRunner._progress_build_message

        def _zh_progress_build_message(self, tool_name, preview, args):
            msg = orig_progress_build_message(self, tool_name, preview, args)
            if msg:
                from agent.display import get_tool_verb, get_tool_emoji
                verb = get_tool_verb(tool_name)
                if verb:
                    emoji = get_tool_emoji(tool_name, default="⚙️")
                    raw_fallback = f"{emoji} {tool_name}..."
                    if msg == raw_fallback:
                        return f"{emoji} {verb}..."
            return msg

        TurnRunner._progress_build_message = _zh_progress_build_message
        TurnRunner._hermes_zh_runner_patched = True
        return True
    except Exception as exc:
        logger.debug("patch_runner failed: %s", exc)
        return False


def patch_gateway_fallback() -> bool:
    """Safely patch gateway text fallback for command approval."""
    try:
        import gateway.run as gr
        if getattr(gr, "_hermes_zh_fallback_patched", False):
            return True

        def _patched_format_exec_approval_fallback(
            command: str, description: str = "dangerous command",
            command_prefix: str = "/", allow_permanent: bool = True,
            allow_session: bool = True, smart_denied: bool = False
        ) -> str:
            cmd_preview = command[:200] + "..." if len(command) > 200 else command
            heading = ("⚠️ **智能拦截 — 管理员覆盖仅适用于本次操作：**" if smart_denied
                       else "⚠️ **需要命令执行审批：**")

            choices = [f"回复 `{command_prefix}approve` 允许本次执行"]
            if not smart_denied and allow_session:
                choices.append(f"`{command_prefix}approve session` 本次会话允许该模式")
                if allow_permanent:
                    choices.append(f"`{command_prefix}approve always` 永久允许")
            choices.append(f"`{command_prefix}deny` 取消执行")

            desc_zh = translate_reason(description)
            return (
                f"{heading}\n```\n{cmd_preview}\n```\n原因: {desc_zh}\n\n"
                + "，".join(choices[:-1]) + f"，或 {choices[-1]}。"
            )

        gr._format_exec_approval_fallback = _patched_format_exec_approval_fallback
        gr._hermes_zh_fallback_patched = True
        return True
    except Exception as exc:
        logger.debug("patch_gateway_fallback skipped: %s", exc)
        return False


def patch_tips() -> bool:
    """Safely patch hermes_cli.tips to use Simplified Chinese tips."""
    _load_tips_data()
    try:
        import hermes_cli.tips as tips_mod
        if getattr(tips_mod, "_hermes_zh_tips_patched", False):
            return True

        if _ZH_TIPS_LIST and len(_ZH_TIPS_LIST) > 0:
            tips_mod._ORIG_TIPS = list(getattr(tips_mod, "TIPS", []))
            tips_mod._ZH_TIPS = _ZH_TIPS_LIST
            tips_mod.TIPS = _ZH_TIPS_LIST

        if _ZH_TIPS_MAP:
            tips_mod._ZH_TIPS_MAP = _ZH_TIPS_MAP

        orig_choice = tips_mod.get_random_tip

        def _zh_get_random_tip(exclude_recent: int = 0) -> str:
            if getattr(tips_mod, "_ZH_TIPS", None):
                import random
                return random.choice(tips_mod._ZH_TIPS)
            raw_tip = orig_choice(exclude_recent)
            tmap = getattr(tips_mod, "_ZH_TIPS_MAP", None) or _ZH_TIPS_MAP
            if tmap and raw_tip in tmap:
                return tmap[raw_tip]
            return raw_tip

        tips_mod.get_random_tip = _zh_get_random_tip
        tips_mod._hermes_zh_tips_patched = True
        return True
    except Exception as exc:
        logger.debug("patch_tips skipped: %s", exc)
        return False


def patch_i18n() -> bool:
    """Inject comprehensive Simplified Chinese translations directly into agent.i18n."""
    try:
        import agent.i18n as i18n_mod
        if getattr(i18n_mod, "_hermes_zh_catalog_hooked", False):
            return True

        def _sanitize_cat(cat: dict[str, str]) -> dict[str, str]:
            for k, v in list(cat.items()):
                if isinstance(v, str) and r"\n" in v:
                    cat[k] = sanitize_literal_newlines(v)
            return cat

        # 1. Load catalog first WITHOUT holding _catalog_lock to prevent deadlock
        # (_load_catalog internally acquires _catalog_lock)
        base_cat = i18n_mod._load_catalog("zh")
        if base_cat:
            _sanitize_cat(base_cat)

        # 2. Safely update _catalog_cache under lock
        with i18n_mod._catalog_lock:
            zh_catalog = i18n_mod._catalog_cache.setdefault("zh", {})
            if base_cat:
                zh_catalog.update(base_cat)
            zh_catalog.update(ZH_I18N_OVERRIDES)
            _sanitize_cat(zh_catalog)

        # 3. Hook _load_catalog for future lookups
        orig_load = i18n_mod._load_catalog

        def _zh_load_catalog(lang: str) -> dict[str, str]:
            cat = orig_load(lang)
            norm = i18n_mod._normalize_lang(lang) if hasattr(i18n_mod, "_normalize_lang") else lang
            if norm == "zh" or lang in ("zh", "zh-cn", "zh-hans", "mandarin", "chinese", "zh-sg"):
                _sanitize_cat(cat)
                cat.update(ZH_I18N_OVERRIDES)
                _sanitize_cat(cat)
            return cat

        i18n_mod._load_catalog = _zh_load_catalog
        i18n_mod._hermes_zh_catalog_hooked = True

        return True
    except Exception as exc:
        logger.warning("patch_i18n failed: %s", exc)
        return False


def patch_command_registry() -> bool:
    """Safely update COMMAND_REGISTRY command descriptions to idiomatic Chinese."""
    try:
        from hermes_cli.commands import COMMAND_REGISTRY
        updated_count = 0
        for cmd in COMMAND_REGISTRY:
            if cmd.name in ZH_COMMAND_DESCRIPTIONS:
                zh_desc = ZH_COMMAND_DESCRIPTIONS[cmd.name]
                if cmd.description != zh_desc:
                    object.__setattr__(cmd, "description", zh_desc)
                    updated_count += 1
        logger.info("Updated %d slash command descriptions to Chinese.", updated_count)
        return True
    except Exception as exc:
        logger.warning("patch_command_registry failed: %s", exc)
        return False


def patch_slash_commands() -> bool:
    """Safely patch non-i18n slash command handlers on GatewaySlashCommandsMixin."""
    try:
        from gateway.slash_commands import GatewaySlashCommandsMixin
        import gateway.slash_commands as gsc

        # 1. Update _BUSY_MODE_BEHAVIOR in-place
        gsc._BUSY_MODE_BEHAVIOR = {
            "queue": ("排队等待下轮执行", "Hermes 忙碌时接收的消息将在本轮任务完成后按队列执行。"),
            "steer": ("在下次工具调用后注入当前任务", "Hermes 忙碌时接收的消息将在下一次工具调用完成后即时注入任务上下文。"),
            "interrupt": ("立即中断当前任务", "Hermes 忙碌时接收的消息将立即中断当前执行的任务。"),
        }

        # 2. Patch _handle_whoami_command
        if not getattr(GatewaySlashCommandsMixin, "_hermes_zh_whoami_patched", False):
            orig_whoami = GatewaySlashCommandsMixin._handle_whoami_command

            async def _zh_handle_whoami_command(self, event: Any) -> str:
                from gateway.slash_access import policy_for_source
                source = event.source
                policy = policy_for_source(self.config, source)
                platform = source.platform.value if source and source.platform else "?"
                chat_type = ((source.chat_type if source else "") or "dm").lower()
                scope = "私聊 (DM)" if chat_type in {"dm", "direct", "private", ""} else "群组/频道 (Group/Channel)"
                user_id = (source.user_id if source else None) or "?"
                head = f"**当前身份** — {platform.title()} ({scope})\n用户 ID: `{user_id}`\n"
                if not policy.enabled:
                    return head + "权限级别: 无限制 (未配置管理员列表)\n可用斜杠指令: 全部可用"
                if policy.is_admin(user_id):
                    return head + "权限级别: **管理员 (admin)**\n可用斜杠指令: 全部可用"
                runnable = list(dict.fromkeys(["help", "whoami"] + sorted(policy.user_allowed_commands)))
                runnable_str = ", ".join(f"/{c}" for c in runnable) if runnable else "(无)"
                return head + f"权限级别: 普通用户 (user)\n您可执行的斜杠指令: {runnable_str}"

            GatewaySlashCommandsMixin._handle_whoami_command = _zh_handle_whoami_command
            GatewaySlashCommandsMixin._hermes_zh_whoami_patched = True

        # 3. Patch _handle_busy_command
        if not getattr(GatewaySlashCommandsMixin, "_hermes_zh_busy_patched", False):
            from gateway.platforms.base import EphemeralReply

            async def _zh_handle_busy_command(self, event: Any):
                arg = event.get_command_args().strip().lower()
                if not arg or arg == "status":
                    mode = self._effective_busy_input_mode(event.source)
                    behavior = gsc._BUSY_MODE_BEHAVIOR.get(mode, gsc._BUSY_MODE_BEHAVIOR["interrupt"])[0]
                    return EphemeralReply(
                        f"**忙碌输入模式：** `{mode}`\n**忙碌期间行为：** _{behavior}_\n"
                        f"切换方式：`/busy queue` (排队)、`/busy steer` (动态注入) 或 `/busy interrupt` (中断)。"
                    )
                if arg not in gsc._BUSY_MODE_BEHAVIOR:
                    return EphemeralReply(
                        f"未知模式 `{arg}`。可用模式：`/busy queue`、`/busy steer` 或 `/busy interrupt`。"
                    )
                from cli import save_config_value
                if not save_config_value("display.busy_input_mode", arg):
                    return EphemeralReply("⚠️ 无法保存 busy_input_mode 到配置。")
                behavior = gsc._BUSY_MODE_BEHAVIOR[arg][1]
                return EphemeralReply(f"✓ 忙碌输入模式已更新为：`{arg}`\n{behavior}")

            GatewaySlashCommandsMixin._handle_busy_command = _zh_handle_busy_command
            GatewaySlashCommandsMixin._hermes_zh_busy_patched = True

        return True
    except Exception as exc:
        logger.debug("patch_slash_commands skipped: %s", exc)
        return False


def wire_telegram_adapter(native: Any, adapter: Any) -> bool:
    """Wire Simplified Chinese settings and interceptors into Telegram adapter when connected."""
    try:
        # Ensure all core standalone patches are applied lazily when Telegram connects
        apply_all()

        # 1. Declarative attributes on the adapter instance
        adapter._EA_HEADER = "⚠️ <b>需要命令执行审批</b>\n\n"
        adapter._EA_REASON_LABEL = "原因: "
        adapter._EA_SMART_DENY_LINE = "\n\n<b>智能拦截：</b>管理员覆盖仅适用于本次单次操作。"
        adapter._EA_ACTION_LABELS = {
            "once": "✅ 仅允许一次",
            "session": "✅ 本会话允许",
            "always": "🔒 永久允许",
            "deny": "❌ 拒绝",
        }

        # 2. Safe format wrapper with strict anti-recursion guard
        if not getattr(adapter, "_hermes_zh_wired", False):
            orig_format = getattr(adapter, "_format_exec_approval", None)
            if orig_format is not None:
                def _zh_format_exec_approval(command: str, description: str = "dangerous command", smart_denied: bool = False) -> str:
                    zh_desc = translate_reason(description)
                    return orig_format(command, zh_desc, smart_denied)

                adapter._format_exec_approval = _zh_format_exec_approval
            adapter._hermes_zh_wired = True
        # 3. Safe callback query & edit wrapper to localize approval resolution ("Approved for session by ...")
        if not getattr(adapter, "_hermes_zh_cb_wired", False):
            orig_edit_md = getattr(adapter, "_edit_md_quiet", None)
            if orig_edit_md is not None:
                async def _zh_edit_md_quiet(query: Any, text_md: str) -> None:
                    return await orig_edit_md(query, translate_approval_resolution(text_md))
                adapter._edit_md_quiet = _zh_edit_md_quiet

            orig_edit_html = getattr(adapter, "_edit_html_quiet", None)
            if orig_edit_html is not None:
                async def _zh_edit_html_quiet(query: Any, text_html: str) -> None:
                    return await orig_edit_html(query, translate_approval_resolution(text_html))
                adapter._edit_html_quiet = _zh_edit_html_quiet

            try:
                from telegram import CallbackQuery
                if not getattr(CallbackQuery, "_hermes_zh_answer_patched", False):
                    orig_answer = CallbackQuery.answer
                    async def _zh_answer(self: Any, *args: Any, **kwargs: Any) -> Any:
                        text = kwargs.get("text")
                        if not text and args:
                            kwargs["text"] = translate_toast_label(args[0])
                            args = args[1:]
                        elif text:
                            kwargs["text"] = translate_toast_label(text)
                        return await orig_answer(self, *args, **kwargs)
                    CallbackQuery.answer = _zh_answer
                    CallbackQuery._hermes_zh_answer_patched = True
            except Exception as exc:
                logger.warning("Failed to patch CallbackQuery.answer: %s", exc)

            adapter._hermes_zh_cb_wired = True

        # 4. Safe model/choice picker & prompt interceptors
        if not getattr(adapter, "_hermes_zh_picker_wired", False):
            orig_send_choice = getattr(adapter, "send_choice_picker", None)
            if orig_send_choice is not None:
                async def _zh_send_choice_picker(chat_id: str, title: str, *args: Any, **kwargs: Any) -> Any:
                    title = sanitize_literal_newlines(title)
                    return await orig_send_choice(chat_id, title, *args, **kwargs)
                adapter.send_choice_picker = _zh_send_choice_picker

            orig_edit_result = getattr(adapter, "_edit_result_text", None)
            if orig_edit_result is not None:
                async def _zh_edit_result_text(query: Any, result_text: str, *args: Any, **kwargs: Any) -> Any:
                    result_text = sanitize_literal_newlines(result_text)
                    return await orig_edit_result(query, result_text, *args, **kwargs)
                adapter._edit_result_text = _zh_edit_result_text

            orig_send_prompt = getattr(adapter, "_send_prompt", None)
            if orig_send_prompt is not None:
                async def _zh_send_prompt(what: str, chat_id: str, metadata: Optional[Dict[str, Any]], build: Any, *args: Any, **kwargs: Any) -> Any:
                    def _wrapped_build() -> Any:
                        built = build()
                        return _translate_prompt_build_result(built)
                    return await orig_send_prompt(what, chat_id, metadata, _wrapped_build, *args, **kwargs)
                adapter._send_prompt = _zh_send_prompt

            orig_picker_edit = getattr(adapter, "_picker_edit", None)
            if orig_picker_edit is not None:
                async def _zh_picker_edit(query: Any, text_md: str, keyboard: Any) -> None:
                    return await orig_picker_edit(
                        query,
                        translate_picker_text(text_md),
                        translate_telegram_keyboard(keyboard),
                    )
                adapter._picker_edit = _zh_picker_edit

            orig_handle_model_cb = getattr(adapter, "_handle_model_picker_callback", None)
            if orig_handle_model_cb is not None:
                async def _zh_handle_model_picker_callback(query: Any, data: str, chat_id: str) -> None:
                    return await orig_handle_model_cb(_LocalizedCallbackQuery(query), data, chat_id)
                adapter._handle_model_picker_callback = _zh_handle_model_picker_callback

            orig_handle_choice_cb = getattr(adapter, "_handle_choice_picker_callback", None)
            if orig_handle_choice_cb is not None:
                async def _zh_handle_choice_picker_callback(query: Any, data: str, chat_id: str) -> None:
                    return await orig_handle_choice_cb(_LocalizedCallbackQuery(query), data, chat_id)
                adapter._handle_choice_picker_callback = _zh_handle_choice_picker_callback

            adapter._hermes_zh_picker_wired = True

        # 5. Safe send & edit_message interceptor for system status, review summaries, & heartbeats
        if not getattr(adapter, "_hermes_zh_send_wired", False):
            orig_send = getattr(adapter, "send", None)
            if orig_send is not None:
                async def _zh_send(chat_id: str, content: str, reply_to: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Any:
                    content_zh = translate_telegram_content(content)
                    return await orig_send(chat_id, content_zh, reply_to=reply_to, metadata=metadata)
                adapter.send = _zh_send

            orig_edit_message = getattr(adapter, "edit_message", None)
            if orig_edit_message is not None:
                async def _zh_edit_message(chat_id: str, message_id: str, content: str, *, finalize: bool = False, metadata: Optional[Dict[str, Any]] = None) -> Any:
                    content_zh = translate_telegram_content(content)
                    return await orig_edit_message(chat_id, message_id, content_zh, finalize=finalize, metadata=metadata)
                adapter.edit_message = _zh_edit_message

            adapter._hermes_zh_send_wired = True
        return True
    except Exception as exc:
        logger.error("wire_telegram_adapter failed: %s", exc, exc_info=True)
        return False


# 12. Context breakdown localization for agent.context_breakdown
ZH_CONTEXT_CATEGORY_MAP: dict[str, str] = {
    "system_prompt": "系统提示词",
    "tool_definitions": "工具定义",
    "rules": "规则指令",
    "skills": "技能",
    "mcp": "MCP 工具",
    "subagent_definitions": "子代理定义",
    "memory": "记忆",
    "conversation": "对话历史",
    "free_space": "剩余空间",
}


def _zh_display_width(s: str) -> int:
    """Calculate terminal display width considering full-width East Asian characters."""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in ("F", "W") else 1 for c in s)


def _zh_pad_label(s: str, target_width: int) -> str:
    """Pad a string to target display width with spaces."""
    dw = _zh_display_width(s)
    if dw < target_width:
        return s + " " * (target_width - dw)
    return s


def zh_render_context_category_lines(payload: Dict[str, Any]) -> list[str]:
    """Render the '按分类预估占用明细' table as plain-text lines with Chinese labels."""
    import agent.context_breakdown as cb

    categories = payload.get("categories") or []
    context_max = int(payload.get("context_max") or 0)
    estimated_total = int(payload.get("estimated_total") or 0)
    denom = context_max or estimated_total

    lines = ["按分类预估占用明细"]
    if not categories:
        return [*lines, "  (暂无数据 — 请先发送一条消息)"]

    free_label = "剩余空间"
    labels = []
    for cat in categories:
        cat_id = str(cat.get("id") or "")
        raw_label = str(cat.get("label") or cat_id)
        label = (
            ZH_CONTEXT_CATEGORY_MAP.get(cat_id)
            or ZH_CONTEXT_CATEGORY_MAP.get(raw_label.lower().replace(" ", "_"))
            or raw_label
        )
        labels.append(label)

    target_width = max(_zh_display_width(free_label), *(_zh_display_width(l) for l in labels))

    for cat, label in zip(categories, labels):
        tokens = int(cat.get("tokens") or 0)
        lines.append(
            f"{cb._glyph(cat)} {_zh_pad_label(label, target_width)} ~{tokens:>9,} Token ~{tokens / denom * 100 if denom else 0.0:>5.1f}%"
        )
    if context_max > 0:
        free = max(0, context_max - estimated_total)
        lines.append(
            f"{cb._FREE_GLYPH} {_zh_pad_label(free_label, target_width)} ~{free:>9,} Token ~{free / context_max * 100:>5.1f}%"
        )
    return lines


def _zh_toolset_row(group: Dict[str, Any]) -> str:
    return f"  {group['toolset']:<24} {group['tool_count']:>3} 个工具 ~{group['schema_tokens']:>8,} Token"


def _zh_skill_row(entry: Dict[str, Any]) -> str:
    name = str(entry.get("name") or "")
    if len(name) > 28:
        name = name[:27] + "…"
    md = entry.get("skill_md_tokens")
    md_str = f"~{md:>8,}" if md is not None else f"{'n/a':>8}"
    return f"  {name:<28} 索引 ~{entry['index_tokens']:>6,}  SKILL.md {md_str} Token"


def _zh_table(lines: list[str], title: str, rows: list[Dict[str, Any]], fmt, limit: int = 15) -> None:
    """Append a titled, display-capped table (blank-separated from a preceding one)."""
    if not rows:
        return
    if lines:
        lines.append("")
    lines.append(title)
    lines.extend(fmt(row) for row in rows[:limit])
    if len(rows) > limit:
        lines.append(f"  … 以及另外 {len(rows) - limit} 项")


def zh_render_context_details_lines(details: Dict[str, Any]) -> list[str]:
    """Render the expanded ``/context all`` per-skill / per-toolset tables in Chinese."""
    import agent.context_breakdown as cb
    lines: list[str] = []
    limit = getattr(cb, "_DETAILS_TABLE_LIMIT", 15)
    _zh_table(lines, "工具集按 Schema 开销排序（由大到小）", details.get("toolsets") or [], _zh_toolset_row, limit)
    _zh_table(lines, "技能按开销排序（索引 = 常驻；SKILL.md = 加载时开销）", details.get("skills") or [], _zh_skill_row, limit)
    return lines


def zh_render_context_breakdown_lines(
    payload: Dict[str, Any],
    *,
    details: Optional[Dict[str, Any]] = None,
    grid: bool = True,
) -> list[str]:
    """Full /context view in Chinese."""
    import agent.context_breakdown as cb

    lines: list[str] = [*cb.render_context_grid(payload), ""] if grid else []
    lines.extend(zh_render_context_category_lines(payload))

    context_max = int(payload.get("context_max") or 0)
    if context_max > 0:
        used, pct = int(payload.get("context_used") or 0), int(payload.get("context_percent") or 0)
        mark = "~" if payload.get("context_estimated") else ""
        lines.extend(["", f"上下文窗口：{mark}{used:,} / {context_max:,} Token ({mark}{pct}%)"])
        source = payload.get("context_source")
        if source:
            labels = {
                "local_estimate": "本地预估",
                "provider_usage": "模型提供商实际用量",
                "provider_usage_plus_estimate": "模型提供商实际用量 + 新消息预估",
            }
            source_zh = labels.get(source, source)
            lines.append(f"数据来源：{source_zh}；分类统计为本地预估。")

    if details is None:
        lines.extend(["", "使用 /context all 查看各技能与工具集的明细开销。"])
    elif detail_lines := zh_render_context_details_lines(details):
        lines.extend(["", *detail_lines])
    return lines


def patch_context_breakdown() -> bool:
    """Safely patch agent.context_breakdown rendering functions to output idiomatic Chinese."""
    try:
        import agent.context_breakdown as cb
        if getattr(cb, "_hermes_zh_context_breakdown_patched", False):
            return True

        # 1. Update display labels in cb._CATEGORIES
        if hasattr(cb, "_CATEGORIES") and isinstance(cb._CATEGORIES, dict):
            for cat_id, val in list(cb._CATEGORIES.items()):
                if isinstance(val, tuple) and len(val) >= 3:
                    lbl, color, glyph = val[0], val[1], val[2]
                    zh_lbl = ZH_CONTEXT_CATEGORY_MAP.get(cat_id, lbl)
                    cb._CATEGORIES[cat_id] = (zh_lbl, color, glyph)

        # 2. Patch renderers
        cb.render_context_category_lines = zh_render_context_category_lines
        cb.render_context_details_lines = zh_render_context_details_lines
        cb.render_context_breakdown_lines = zh_render_context_breakdown_lines
        if hasattr(cb, "_toolset_row"):
            cb._toolset_row = _zh_toolset_row
        if hasattr(cb, "_skill_row"):
            cb._skill_row = _zh_skill_row
        if hasattr(cb, "_table"):
            cb._table = _zh_table

        cb._hermes_zh_context_breakdown_patched = True
        return True
    except Exception as exc:
        logger.warning("patch_context_breakdown failed: %s", exc)
        return False

def patch_fallback_notice() -> bool:
    """Safely patch StatusOutputMixin._emit_pending_fallback_notice to translate fallback messages."""
    try:
        from agent.status_output import StatusOutputMixin
        if getattr(StatusOutputMixin, "_hermes_zh_fallback_patched", False):
            return True
        orig_fn = getattr(StatusOutputMixin, "_emit_pending_fallback_notice", None)
        if orig_fn is None:
            return False

        def _zh_emit_pending_fallback_notice(self: Any) -> None:
            notice = getattr(self, "_pending_fallback_notice", None)
            if not notice:
                return
            if isinstance(notice, list):
                self._pending_fallback_notice = [translate_fallback_notice(str(n)) for n in notice]
            else:
                self._pending_fallback_notice = translate_fallback_notice(str(notice))
            return orig_fn(self)

        StatusOutputMixin._emit_pending_fallback_notice = _zh_emit_pending_fallback_notice
        StatusOutputMixin._hermes_zh_fallback_patched = True
        return True
    except Exception as exc:
        logger.debug("patch_fallback_notice skipped: %s", exc)
        return False


_hermes_zh_all_applied = False


def apply_all() -> bool:
    """Apply standalone patches (display verbs, builders, fallback, activity, runner, review, tips, i18n, registry, slash, context_breakdown, fallback_notice) idempotently."""
    global _hermes_zh_all_applied
    if _hermes_zh_all_applied:
        return True
    ok1 = patch_display()
    ok2 = patch_gateway_fallback()
    ok3 = patch_activity()
    ok4 = patch_background_review()
    ok5 = patch_runner()
    ok6 = patch_tips()
    ok7 = patch_i18n()
    ok8 = patch_command_registry()
    ok9 = patch_slash_commands()
    ok10 = patch_context_breakdown()
    ok11 = patch_fallback_notice()
    _hermes_zh_all_applied = True
    return ok1 or ok2 or ok3 or ok4 or ok5 or ok6 or ok7 or ok8 or ok9 or ok10 or ok11
