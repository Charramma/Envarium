"""平台适配端口：新增平台只需实现该协议。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from envarium.core.models import Environment


class PlatformProvider(Protocol):
    """发现本机上所有 Python 环境。"""

    def discover_installations(self) -> list[Environment]:
        """枚举系统安装的 Python 解释器（含 conda 发行版）。"""
        ...

    def discover_conda_environments(self) -> list[Environment]:
        """枚举 conda 环境（含 base）。"""
        ...

    def scan_virtualenvs(self, roots: Sequence[Path]) -> list[Environment]:
        """扫描指定根目录下的 venv 环境。"""
        ...
