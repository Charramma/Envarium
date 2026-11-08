"""venv 发现：以 pyvenv.cfg 为唯一强信号，限定深度扫描。"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator, Sequence
from pathlib import Path

from envarium.core.models import Environment, EnvKind

logger = logging.getLogger(__name__)

DEFAULT_MAX_DEPTH = 3

# 既非 venv 又通常体积庞大的目录，扫描时跳过
_SKIPPED_DIR_NAMES = frozenset(
    {
        "$Recycle.Bin",
        ".git",
        ".hg",
        ".svn",
        "AppData",
        "Application Data",
        "node_modules",
        "Program Files",
        "Program Files (x86)",
        "System Volume Information",
        "Windows",
        "__pycache__",
    }
)


def read_pyvenv_cfg(cfg_path: Path) -> dict[str, str]:
    """解析 pyvenv.cfg 的 key = value 结构。"""
    values: dict[str, str] = {}
    for line in cfg_path.read_text(encoding="utf-8", errors="replace").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip()
    return values


def _subdirectories(directory: Path) -> Iterator[Path]:
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name in _SKIPPED_DIR_NAMES:
                    continue
                if entry.is_dir(follow_symlinks=False):
                    yield Path(entry.path)
    except OSError:
        logger.debug("目录不可访问：%s", directory)


def _read_virtualenv(path: Path) -> Environment | None:
    interpreter = path / "Scripts" / "python.exe"
    if not interpreter.is_file():
        return None
    return Environment(
        name=path.name,
        path=path,
        kind=EnvKind.VENV,
        version=read_pyvenv_cfg(path / "pyvenv.cfg").get("version", ""),
        interpreter=interpreter,
    )


def _walk(root: Path, max_depth: int) -> Iterator[Environment]:
    stack = [(root, 0)]
    while stack:
        directory, depth = stack.pop()
        if (directory / "pyvenv.cfg").is_file():
            environment = _read_virtualenv(directory)
            if environment is not None:
                yield environment
            continue
        if depth >= max_depth:
            continue
        stack.extend((child, depth + 1) for child in _subdirectories(directory))


def scan_virtualenvs(
    roots: Sequence[Path], max_depth: int = DEFAULT_MAX_DEPTH
) -> list[Environment]:
    """扫描给定根目录下所有 venv 环境。"""
    environments: dict[str, Environment] = {}
    for root in roots:
        if not root.is_dir():
            logger.debug("扫描根目录不存在：%s", root)
            continue
        for environment in _walk(root, max_depth):
            environments.setdefault(environment.key, environment)
    return list(environments.values())
