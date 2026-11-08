"""领域模型：整个应用对「Python 环境」的唯一定义源。"""

from __future__ import annotations

import os
from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class EnvKind(StrEnum):
    """环境类型。"""

    PYTHON = "python"
    CONDA = "conda"
    VENV = "venv"


class TerminalKind(StrEnum):
    """可唤起的外部终端。"""

    POWERSHELL = "powershell"
    CMD = "cmd"
    WINDOWS_TERMINAL = "windows_terminal"


class ExportFormat(StrEnum):
    """环境信息的导出格式。"""

    REQUIREMENTS = "requirements"
    CONDA_ENV = "conda_env"
    JSON = "json"

    @property
    def file_name(self) -> str:
        return {
            ExportFormat.REQUIREMENTS: "requirements.txt",
            ExportFormat.CONDA_ENV: "environment.yml",
            ExportFormat.JSON: "environment.json",
        }[self]


def normalize_path(path: Path) -> str:
    """路径比较与去重的规范形式（Windows 下大小写不敏感）。"""
    return os.path.normcase(os.path.abspath(path))


class Environment(BaseModel):
    """一个可用的 Python 环境。"""

    model_config = ConfigDict(frozen=True)

    name: str
    path: Path
    kind: EnvKind
    version: str
    interpreter: Path
    is_base: bool = False
    available: bool = True
    on_path: bool = False

    @property
    def key(self) -> str:
        return normalize_path(self.path)

    @property
    def removable(self) -> bool:
        """系统安装解释器与 conda base 不可重建，不提供删除。"""
        return self.kind is not EnvKind.PYTHON and not self.is_base

    @property
    def renamable(self) -> bool:
        return self.removable

    @property
    def cloneable(self) -> bool:
        return self.kind is EnvKind.CONDA and not self.is_base


class Package(BaseModel):
    """环境中的一个已安装包。"""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str


class EnvironmentMetrics(BaseModel):
    """环境目录的占用空间、最近修改时间与可写性。"""

    model_config = ConfigDict(frozen=True)

    size_bytes: int
    modified_at: datetime
    writable: bool


class PackageDiff(BaseModel):
    """同一包在两个环境中的版本差异。"""

    model_config = ConfigDict(frozen=True)

    name: str
    left_version: str = ""
    right_version: str = ""

    @property
    def differs(self) -> bool:
        return self.left_version != self.right_version



def dedupe_environments(environments: Iterable[Environment]) -> list[Environment]:
    """按环境路径去重，同一路径保留首次出现的记录。"""
    unique: dict[str, Environment] = {}
    for environment in environments:
        unique.setdefault(environment.key, environment)
    return list(unique.values())
