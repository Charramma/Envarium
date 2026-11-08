"""conda 集成：只通过 CLI 与 --json 交互，不依赖 import conda。"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from pathlib import Path

from envarium.core.models import Environment, EnvKind, normalize_path
from envarium.infrastructure.subprocess_runner import SubprocessRunner

logger = logging.getLogger(__name__)

_PYTHON_DISTRIBUTION_DIRS = ("anaconda3", "miniconda3", "Anaconda3", "Miniconda3")
_PYTHON_META_VERSION = re.compile(r"^python-(\d+\.\d+\.\d+)-")


def find_conda() -> Path | None:
    """定位 conda 可执行文件：PATH 优先，其次常见安装目录。"""
    on_path = shutil.which("conda")
    if on_path:
        return Path(on_path)

    home = Path.home()
    local_app_data = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    program_data = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
    candidates = [
        base / name / "Scripts" / "conda.exe"
        for base in (home, local_app_data, program_data)
        for name in _PYTHON_DISTRIBUTION_DIRS
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def read_conda_python_version(env_path: Path) -> str:
    """从 conda-meta 文件名读取 Python 版本，避免额外的 conda 子进程调用。"""
    meta_dir = env_path / "conda-meta"
    if not meta_dir.is_dir():
        return ""
    for meta_file in meta_dir.glob("python-3*.json"):
        match = _PYTHON_META_VERSION.match(meta_file.name)
        if match:
            return match.group(1)
    return ""


def _root_prefix(runner: SubprocessRunner, executable: Path) -> Path | None:
    result = runner.run([executable, "info", "--json"])
    if not result.ok:
        logger.warning("conda info 失败：%s", result.stderr.strip())
        return None
    prefix = json.loads(result.stdout).get("root_prefix")
    return Path(prefix) if prefix else None


def _build_environment(path: Path, root_prefix: Path | None) -> Environment | None:
    interpreter = path / "python.exe"
    if not interpreter.is_file():
        return None
    is_base = root_prefix is not None and normalize_path(path) == normalize_path(root_prefix)
    return Environment(
        name="base" if is_base else path.name,
        path=path,
        kind=EnvKind.CONDA,
        version=read_conda_python_version(path),
        interpreter=interpreter,
        is_base=is_base,
    )


def list_conda_environments(runner: SubprocessRunner, executable: Path) -> list[Environment]:
    """通过 conda env list --json 枚举全部环境。"""
    result = runner.run([executable, "env", "list", "--json"])
    if not result.ok:
        logger.warning("conda env list 失败：%s", result.stderr.strip())
        return []

    root_prefix = _root_prefix(runner, executable)
    environments: list[Environment] = []
    for raw_path in json.loads(result.stdout).get("envs", []):
        environment = _build_environment(Path(raw_path), root_prefix)
        if environment is not None:
            environments.append(environment)
    return environments
