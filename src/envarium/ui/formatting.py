"""界面展示格式化：大小与时间的唯一格式来源。"""

from __future__ import annotations

from datetime import datetime

_UNITS = ("B", "KB", "MB", "GB", "TB")


def format_size(size_bytes: int) -> str:
    value = float(size_bytes)
    for unit in _UNITS[:-1]:
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} {_UNITS[-1]}"


def format_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


def breakable_path(path: str) -> str:
    """在路径分隔符后插入换行机会，使长路径在窄区域中完整换行显示。"""
    return path.replace("\\", "\\\u200b").replace("/", "/\u200b")
