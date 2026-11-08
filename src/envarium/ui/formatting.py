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
