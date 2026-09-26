"""Hermes-zh plugin: Version checker strictly aligned with Official Curated Catalog.

Conforms strictly to Hermes plugin guidelines:
1. Pure lazy loading (zero network/eager requests at import or register time).
2. Sole version source: Hermes Official Curated Catalog (LIVE_CATALOG_URL).
3. Short network timeout (<= 1.5s) preventing slash command response blocking.
4. Local TTL caching (6 hours) reducing unnecessary remote round-trips.
5. Failure cooldown (60s) preventing consecutive timeout stalls on network drops.
6. Semantic versioning (SemVer) with -dev / prerelease support.
7. Isolated developer test mode for interactive card UI testing.
8. Cross-platform standardized output without any emoji.

Author: Cody
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("hermes_zh.version_checker")

PLUGIN_NAME = "hermes-zh"
LIVE_CATALOG_URL = "https://hermes-agent.nousresearch.com/docs/api/plugin-catalog.json"

LIVE_CATALOG_TTL_SECONDS = 6 * 60 * 60  # 6 小时本地缓存
LIVE_CATALOG_FAILURE_TTL_SECONDS = 60.0  # 失败冷却时间 60 秒
REQUEST_TIMEOUT = 1.5  # 短超时 <= 1.5 秒
MAX_CATALOG_BYTES = 2 * 1024 * 1024  # 最大允许读取 2MB

# 模块级最后失败时间戳，防止网络异常时频繁重试卡死
_last_failure_time: float = 0.0


def reset_failure_cooldown() -> None:
    """重置网络失败冷却计时器（供测试或强制刷新调用）。"""
    global _last_failure_time
    _last_failure_time = 0.0


def clear_local_cache() -> None:
    """清除本地版本缓存文件（供测试或强制重置调用）。"""
    try:
        p = get_dedicated_cache_path()
        if p.is_file():
            p.unlink()
    except Exception:
        pass


def get_cache_dir() -> Path:
    """获取 Hermes 缓存目录。"""
    try:
        from hermes_constants import get_hermes_home
        cache_dir = get_hermes_home() / "cache"
    except Exception:
        hermes_home = os.environ.get("HERMES_HOME")
        if hermes_home:
            cache_dir = Path(hermes_home) / "cache"
        else:
            cache_dir = Path.home() / ".hermes" / "cache"

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir
    except Exception:
        tmp_dir = Path(tempfile.gettempdir()) / "hermes_cache"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        return tmp_dir


def get_dedicated_cache_path() -> Path:
    """获取 hermes-zh 专属版本缓存路径。"""
    return get_cache_dir() / "hermes-zh-catalog.json"


def get_official_catalog_cache_path() -> Path:
    """获取 Hermes 官方主程序 catalog 缓存路径。"""
    return get_cache_dir() / "plugin-catalog.json"


class SemVerTuple(tuple):
    """语义化版本元组，继承自 tuple 并增强支持 -dev、-alpha、-rc 等预发布标识的比对。

    保持对原有 (major, minor, patch) 纯数字元组的 100% 向后兼容：
    - 当与普通 tuple 比较时，若自身为正式版本且核心数字段相同，等价判定为相等；
    - 严格遵循 SemVer 2.0 规范：正式版 > 预发布版 (例如 0.1.4 > 0.1.4-dev > 0.1.3)。
    """

    def __new__(cls, core_tuple: Tuple[int, ...], prerelease: Optional[str] = None, raw: str = ""):
        obj = super().__new__(cls, core_tuple)
        obj.prerelease = prerelease
        obj.raw = raw
        return obj

    def _cmp_key(self) -> tuple[Any, ...]:
        is_release = 1 if self.prerelease is None else 0
        pre_tokens = []
        if self.prerelease:
            for part in str(self.prerelease).split("."):
                if part.isdigit():
                    pre_tokens.append((0, int(part), ""))
                else:
                    pre_tokens.append((1, 0, part))
        return (tuple(self[:3]), is_release, tuple(pre_tokens))

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, SemVerTuple):
            if isinstance(other, tuple):
                other = SemVerTuple(other)
            elif isinstance(other, str):
                other = parse_version(other)
            else:
                return NotImplemented
        return self._cmp_key() < other._cmp_key()

    def __le__(self, other: Any) -> bool:
        return self == other or self < other

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, SemVerTuple):
            if isinstance(other, tuple):
                other = SemVerTuple(other)
            elif isinstance(other, str):
                other = parse_version(other)
            else:
                return NotImplemented
        return self._cmp_key() > other._cmp_key()

    def __ge__(self, other: Any) -> bool:
        return self == other or self > other

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, SemVerTuple):
            return self._cmp_key() == other._cmp_key()
        if isinstance(other, tuple):
            return self.prerelease is None and tuple(self) == other
        if isinstance(other, str):
            return self == parse_version(other)
        return False

    def __ne__(self, other: Any) -> bool:
        return not (self == other)


def parse_version(v: str) -> SemVerTuple:
    """解析版本字符串为 SemVerTuple，支持数字元组与 -dev 等预发布标识。"""
    clean = str(v).strip().lstrip("vV")
    clean = clean.split("+")[0]
    parts = clean.split("-", 1)
    core_str = parts[0]
    prerelease = parts[1].strip() if len(parts) > 1 else None

    segments = re.findall(r"\d+", core_str)
    core = tuple(int(x) for x in segments) if segments else (0,)
    return SemVerTuple(core, prerelease=prerelease, raw=str(v))


def is_newer_version(latest: str, current: str) -> bool:
    """对比版本号，判断 latest 是否严格大于 current。

    全面遵循语义化版本 (SemVer) 规范：
    1. 精准解析与比对 -dev、-alpha、-rc 等预发布版本；
    2. 例如 0.1.4-dev 严格高于 0.1.3，但低于正式发布版 0.1.4；
    3. 支持带 v/V 前缀版本号。
    """
    try:
        v_latest = parse_version(latest)
        v_curr = parse_version(current)
        return v_latest > v_curr
    except Exception:
        return False


def _extract_version_from_entries(entries: Any) -> Optional[str]:
    """从 catalog entries 列表中提取 hermes-zh 的版本号。"""
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == PLUGIN_NAME:
            ver = entry.get("version")
            if ver and isinstance(ver, str):
                return ver.strip().lstrip("vV")
    return None


def read_local_cached_version(
    max_age_seconds: float = LIVE_CATALOG_TTL_SECONDS,
) -> Tuple[Optional[str], bool]:
    """读取本地缓存的版本号。

    返回元组 (version, is_fresh):
    - version: 缓存中的版本字符串，若无则为 None；
    - is_fresh: 缓存是否在 max_age_seconds 有效期内。
    """
    now = time.time()
    stale_version: Optional[str] = None

    # 1. 优先检查 hermes-zh 专属缓存
    dedicated = get_dedicated_cache_path()
    if dedicated.is_file():
        try:
            data = json.loads(dedicated.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                ver = data.get("version")
                ts = float(data.get("timestamp", 0.0))
                if ver and isinstance(ver, str):
                    clean_ver = ver.strip().lstrip("vV")
                    if (now - ts) < max_age_seconds:
                        return clean_ver, True
                    stale_version = clean_ver
        except Exception as e:
            logger.debug("读取专属版本缓存失败: %s", e)

    # 2. 检查 Hermes 官方主程序 catalog 缓存
    official = get_official_catalog_cache_path()
    if official.is_file():
        try:
            mtime = official.stat().st_mtime
            data = json.loads(official.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                ver = _extract_version_from_entries(data.get("entries"))
                if ver:
                    if (now - mtime) < max_age_seconds:
                        return ver, True
                    if not stale_version:
                        stale_version = ver
        except Exception as e:
            logger.debug("读取官方 catalog 缓存失败: %s", e)

    return stale_version, False


def write_local_cached_version(version: str) -> bool:
    """将最新版本信息写入专属缓存。"""
    try:
        path = get_dedicated_cache_path()
        clean_ver = str(version).strip().lstrip("vV")
        payload = {
            "name": PLUGIN_NAME,
            "version": clean_ver,
            "timestamp": time.time(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        logger.debug("写入专属版本缓存失败: %s", e)
        return False


def fetch_catalog_version_online(
    timeout: float = REQUEST_TIMEOUT,
    current_version: str = "",
) -> Optional[str]:
    """在线请求官方社区插件目录获取最新版本。

    严格遵循短超时（<= 1.5s）与网络失败保护，失败时静默降级为 None，
    绝不阻塞主程序或抛出未捕获异常。
    """
    global _last_failure_time
    now = time.time()
    if now < (_last_failure_time + LIVE_CATALOG_FAILURE_TTL_SECONDS):
        logger.debug("处于网络失败冷却期，跳过在线检测")
        return None

    try:
        user_agent = f"hermes-zh/{current_version}" if current_version else "hermes-zh"
        req = urllib.request.Request(
            LIVE_CATALOG_URL,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                _last_failure_time = time.time()
                return None
            raw_bytes = resp.read(MAX_CATALOG_BYTES)
            data = json.loads(raw_bytes.decode("utf-8"))
            ver = _extract_version_from_entries(data.get("entries"))
            if ver:
                write_local_cached_version(ver)
                return ver
    except Exception as e:
        _last_failure_time = time.time()
        logger.debug("在线请求官方 Catalog 失败或超时: %s", e)
        return None
    return None


def get_latest_catalog_version(
    timeout: float = REQUEST_TIMEOUT,
    current_version: str = "",
    force_refresh: bool = False,
) -> Optional[str]:
    """获取官方目录最新版本号。

    检测策略：
    1. 非强制刷新下优先读取未过期的本地缓存；
    2. 缓存失效或强制刷新时，发起短超时在线请求；
    3. 在线请求成功则更新本地缓存并返回；
    4. 在线请求失败时，尝试降级读取陈旧缓存；
    5. 无可用缓存且网络异常时，平滑返回 None，完全零破坏、零报错。
    """
    if not force_refresh:
        cached_ver, is_fresh = read_local_cached_version()
        if cached_ver and is_fresh:
            return cached_ver

    online_ver = fetch_catalog_version_online(timeout=timeout, current_version=current_version)
    if online_ver:
        return online_ver

    stale_ver, _ = read_local_cached_version(max_age_seconds=float("inf"))
    return stale_ver


def is_test_command(raw_args: str) -> bool:
    """判断是否为测试模式指令（例如 test, --test, -t, mock, --mock）。"""
    tokens = str(raw_args).strip().lower().split()
    return any(t in ("test", "--test", "-t", "mock", "--mock") for t in tokens)


def generate_mock_newer_version(current_version: str) -> str:
    """生成严格高于当前版本的模拟版本号（供测试交互弹卡流程）。"""
    clean = str(current_version).strip().lstrip("vV")
    parsed = parse_version(clean)

    # 预发布版提升为同级正式版
    if parsed.prerelease:
        core_str = ".".join(str(x) for x in parsed[:3]) if len(parsed) >= 3 else clean.split("-")[0]
        return core_str

    # 正式版将末位版本号递增 1
    if len(parsed) >= 3:
        return f"{parsed[0]}.{parsed[1]}.{parsed[2] + 1}"
    elif len(parsed) == 2:
        return f"{parsed[0]}.{parsed[1] + 1}.0"
    return f"{parsed[0]}.1.0"


class CheckResult:
    """版本检测结果封装类。"""

    def __init__(
        self,
        current_version: str,
        latest_version: str,
        has_update: bool,
        is_test: bool = False,
        source: str = "none",  # curated | cache | mock | none
    ):
        self.current_version = current_version
        self.latest_version = latest_version
        self.has_update = has_update
        self.is_test = is_test
        self.source = source  # curated | cache | mock | none

    def __repr__(self) -> str:
        return (
            f"<CheckResult curr={self.current_version} latest={self.latest_version} "
            f"has_update={self.has_update} test={self.is_test} src={self.source}>"
        )


def check_update(
    current_version: str,
    raw_args: str = "",
    force_refresh: bool = False,
    timeout: float = REQUEST_TIMEOUT,
) -> CheckResult:
    """统一版本检测入口：严格对齐 Hermes 官方社区插件库（Curated Catalog）。

    1. 开发者测试模式隔离：仅在用户显式传入测试参数时触发模拟新版弹卡；
    2. 默认执行模式：100% 走官方 Catalog 真实判定，严禁越俎代庖；
    3. 仅当官方社区库中收录的版本严格高于当前本地版本时，才判定存在新版本；
    4. 保持 <= 1.5s 短超时、6 小时本地 TTL 缓存与失败冷却容灾机制。
    """
    clean_curr = str(current_version).strip().lstrip("vV")
    is_test = is_test_command(raw_args)

    # 1. 开发者测试模式严格隔离：仅在用户显式传入测试参数时触发模拟新版
    if is_test:
        mock_ver = generate_mock_newer_version(clean_curr)
        return CheckResult(
            current_version=clean_curr,
            latest_version=mock_ver,
            has_update=True,
            is_test=True,
            source="mock",
        )

    # 2. 默认执行模式：100% 走官方 Catalog 真实判定
    force = force_refresh or str(raw_args).strip().lower() in ("check", "refresh", "-f", "--force")
    catalog_ver = get_latest_catalog_version(timeout=timeout, current_version=clean_curr, force_refresh=force)

    if catalog_ver and is_newer_version(catalog_ver, clean_curr):
        return CheckResult(
            current_version=clean_curr,
            latest_version=catalog_ver,
            has_update=True,
            is_test=False,
            source="curated",
        )

    latest_seen = catalog_ver or clean_curr
    return CheckResult(
        current_version=clean_curr,
        latest_version=latest_seen,
        has_update=False,
        is_test=False,
        source="curated" if catalog_ver else "none",
    )


def format_status_message(current_version: str, latest_version: Optional[str] = None) -> str:
    """生成标准化跨平台展示文本。

    严禁出现任何 emoji 表情，保证在 CLI、Telegram、Discord、Slack 均能整齐渲染。
    """
    v_curr = f"v{str(current_version).strip().lstrip('vV')}"
    lines = [
        f"{PLUGIN_NAME} 汉化插件",
        f"当前版本：{v_curr}",
    ]

    if latest_version and is_newer_version(latest_version, current_version):
        v_latest = f"v{str(latest_version).strip().lstrip('vV')}"
        lines.extend([
            f"有新版{v_latest}",
            f"更新指令：hermes plugins update {PLUGIN_NAME}",
        ])
    lines.append("问题反馈：https://github.com/Cody292/hermes-zh/issues")
    return "\n".join(lines)


def format_card_fallback_text(
    current_version: str,
    latest_version: str,
    is_test: bool = False,
) -> str:
    """生成标准化跨平台纯文本/CLI降级文本。

    严禁出现任何 emoji 表情。
    """
    v_curr = f"v{str(current_version).strip().lstrip('vV')}"
    v_latest = f"v{str(latest_version).strip().lstrip('vV')}"
    test_tag = " [测试模拟]" if is_test else ""
    lines = [
        f"{PLUGIN_NAME} 汉化插件{test_tag}",
        f"当前版本：{v_curr}",
        f"有新版{v_latest}",
    ]
    if is_test:
        lines.append("测试说明：此为测试模拟卡片降级展示，支持使用 Telegram 真实点击验证交互")
    lines.extend([
        f"更新指令：hermes plugins update {PLUGIN_NAME}",
        "问题反馈：https://github.com/Cody292/hermes-zh/issues",
    ])
    return "\n".join(lines)
