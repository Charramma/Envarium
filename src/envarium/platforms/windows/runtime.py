"""Windows 运行时探测：操作系统版本、系统 Python 的 pip 与 conda 版本。"""

from __future__ import annotations

import platform
import re
from collections.abc import Sequence
from pathlib import Path

from envarium.core.errors import AppError
from envarium.core.models import (
    CondaRuntime,
    Environment,
    EnvKind,
    PythonToolchain,
    SystemInfo,
)
from envarium.core.ports import LineSink
from envarium.infrastructure.subprocess_runner import SubprocessRunner
from envarium.platforms.windows.conda_adapter import find_conda

_WINDOWS_11_BUILD = 22000
_ARCHITECTURES = {"AMD64": "x64", "ARM64": "arm64", "x86": "x86"}
_PIP_VERSION = re.compile(r"^pip\s+(\S+)\s+from\s+(.+?)\s+\(python", re.IGNORECASE)
_CONDA_VERSION = re.compile(r"conda\s+(\S+)")


def describe_system(name: str, release: str, version: str, machine: str) -> SystemInfo:
    """把 platform 的原始标识收敛为「Windows 11 / x64」形式。"""
    parts = version.split(".")
    build = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 0
    display_release = "11" if build >= _WINDOWS_11_BUILD else release
    architecture = _ARCHITECTURES.get(machine, machine.lower() or "unknown")
    return SystemInfo(
        name=name,
        release=display_release,
        version=version,
        machine=architecture,
        display=f"{name} {display_release} / {architecture}",
    )


def parse_pip_version(output: str) -> tuple[str, Path | None]:
    """解析 `pip 25.2 from <路径> (python 3.13)`。"""
    match = _PIP_VERSION.search(output)
    if match is None:
        return "", None
    return match.group(1), Path(match.group(2))


def parse_conda_version(output: str) -> str:
    """解析 `conda 24.9.2`。"""
    match = _CONDA_VERSION.search(output)
    return match.group(1) if match else ""


class WindowsRuntimeProbe:
    """实现 RuntimeProbe 协议。"""

    def __init__(self, runner: SubprocessRunner, conda: Path | None = None) -> None:
        self._runner = runner
        self._conda_path = conda

    def system_info(self) -> SystemInfo:
        return describe_system(
            platform.system(), platform.release(), platform.version(), platform.machine()
        )

    def python_toolchains(self, installations: Sequence[Environment]) -> list[PythonToolchain]:
        toolchains: list[PythonToolchain] = []
        for environment in installations:
            if environment.kind is not EnvKind.PYTHON:
                continue
            result = self._runner.run([environment.interpreter, "-m", "pip", "--version"])
            version, path = parse_pip_version(result.stdout) if result.ok else ("", None)
            toolchains.append(
                PythonToolchain(environment=environment, pip_version=version, pip_path=path)
            )
        return toolchains

    def conda_runtime(self) -> CondaRuntime | None:
        executable = self._conda_path or find_conda()
        if executable is None:
            return None
        result = self._runner.run([executable, "--version"])
        version = parse_conda_version(result.stdout) if result.ok else ""
        return CondaRuntime(executable=executable, version=version)

    def upgrade_pip(self, interpreter: Path, log: LineSink) -> None:
        returncode = self._runner.stream(
            [interpreter, "-m", "pip", "install", "--upgrade", "pip"], on_line=log
        )
        if returncode != 0:
            raise AppError(f"pip 升级失败（返回码 {returncode}），详见运行日志。")
