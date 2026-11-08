"""Windows 平台 Provider：组合三类发现来源。"""

from __future__ import annotations

import itertools
import shutil
from collections.abc import Sequence
from pathlib import Path

from envarium.core.models import Environment, dedupe_environments
from envarium.infrastructure.subprocess_runner import SubprocessRunner
from envarium.platforms.windows.conda_adapter import find_conda, list_conda_environments
from envarium.platforms.windows.installations import (
    discover_launcher_pythons,
    discover_registered_pythons,
)
from envarium.platforms.windows.venv_scanner import scan_virtualenvs


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
