"""Windows 平台 Provider：组合三类发现来源，并识别手动指定的目录。"""

from __future__ import annotations

import itertools
import logging
import shutil
from collections.abc import Sequence
from pathlib import Path

from envarium.core.models import Environment, EnvKind, dedupe_environments
from envarium.infrastructure.subprocess_runner import SubprocessRunner
from envarium.platforms.windows.conda_adapter import (
    build_environment,
    find_conda,
    list_conda_environments,
    read_root_prefix,
)
from envarium.platforms.windows.installations import (
    discover_launcher_pythons,
    discover_registered_pythons,
)
from envarium.platforms.windows.venv_scanner import read_venv_version, scan_virtualenvs

logger = logging.getLogger(__name__)


class WindowsProvider:
    """实现 PlatformProvider 协议。"""

    def __init__(self, runner: SubprocessRunner) -> None:
        self._runner = runner

    def discover_installations(self) -> list[Environment]:
        launcher = shutil.which("py")
        return dedupe_environments(
            itertools.chain(
                discover_registered_pythons(),
                discover_launcher_pythons(self._runner, Path(launcher) if launcher else None),
            )
        )

    def discover_conda_environments(self) -> list[Environment]:
        executable = find_conda()
        if executable is None:
            return []
        return list_conda_environments(self._runner, executable)

    def scan_virtualenvs(self, roots: Sequence[Path]) -> list[Environment]:
        return scan_virtualenvs(roots)

    def inspect(self, path: Path) -> Environment | None:
        if not path.is_dir():
            return None

        if (path / "conda-meta").is_dir():
            executable = find_conda()
            root_prefix = (
                read_root_prefix(self._runner, executable) if executable is not None else None
            )
            return build_environment(path, root_prefix)

        cfg_path = path / "pyvenv.cfg"
        if cfg_path.is_file():
            venv_interpreter = path / "Scripts" / "python.exe"
            if not venv_interpreter.is_file():
                return None
            return Environment(
                name=path.name,
                path=path,
                kind=EnvKind.VENV,
                version=read_venv_version(cfg_path),
                interpreter=venv_interpreter,
            )

        interpreter = path / "python.exe"
        if not interpreter.is_file():
            return None
        return Environment(
            name=path.name,
            path=path,
            kind=EnvKind.PYTHON,
            version=self._read_python_version(interpreter),
            interpreter=interpreter,
        )

    def _read_python_version(self, interpreter: Path) -> str:
        result = self._runner.run(
            [interpreter, "-c", "import platform; print(platform.python_version())"]
        )
        if not result.ok:
            logger.debug("读取 Python 版本失败：%s", result.stderr.strip())
            return ""
        return result.stdout.strip()
