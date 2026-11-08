"""领域模型：整个应用对「Python 环境」的唯一定义源。"""

from __future__ import annotations

import os
from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class EnvKind(StrEnum):
    """环境类型。"""

    PYTHON = "python"
    CONDA = "conda"
    VENV = "venv"


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

    @property
    def key(self) -> str:
        return normalize_path(self.path)


def dedupe_environments(environments: Iterable[Environment]) -> list[Environment]:
    """按环境路径去重，同一路径保留首次出现的记录。"""
    unique: dict[str, Environment] = {}
    for environment in environments:
        unique.setdefault(environment.key, environment)
    return list(unique.values())
