"""平台适配端口：新增平台只需实现这些协议。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from envarium.core.mirrors import Mirror
from envarium.core.models import (
    CondaChannel,
    CondaRuntime,
    Environment,
    Package,
    PythonToolchain,
    SystemInfo,
    TerminalKind,
)

LineSink = Callable[[str], None]


class PlatformProvider(Protocol):
    """发现本机上的 Python 环境，并解释单个环境目录。"""

    def discover_installations(self) -> list[Environment]:
        """枚举系统安装的 Python 解释器（含 conda 发行版）。"""
        ...

    def discover_conda_environments(self) -> list[Environment]:
        """枚举 conda 环境（含 base）。"""
        ...

    def inspect(self, path: Path) -> Environment | None:
        """把用户指定的目录识别为环境；无法识别时返回 None。"""
        ...


class EnvironmentOperator(Protocol):
    """对环境执行创建、变更与外部程序唤起。"""

    def create_venv(
        self, interpreter: Path, target: Path, *, system_site_packages: bool
    ) -> None: ...

    def create_conda(
        self, name: str, python_version: str, channel: CondaChannel
    ) -> None: ...

    def list_conda_python_versions(self, channel: CondaChannel) -> list[str]: ...

    def remove(self, environment: Environment) -> None: ...

    def rename(self, environment: Environment, new_name: str) -> None: ...

    def clone(self, environment: Environment, new_name: str) -> None: ...

    def list_packages(self, environment: Environment) -> list[Package]: ...

    def install(self, environment: Environment, specs: Sequence[str], log: LineSink) -> None: ...

    def uninstall(self, environment: Environment, name: str, log: LineSink) -> None: ...

    def configure_mirror(self, mirror: Mirror) -> None: ...

    def open_terminal(self, environment: Environment, terminal: TerminalKind) -> None: ...


class RuntimeProbe(Protocol):
    """探测操作系统、系统 Python 的 pip、conda 运行时。"""

    def system_info(self) -> SystemInfo: ...

    def python_toolchains(
        self, installations: Sequence[Environment]
    ) -> list[PythonToolchain]: ...

    def conda_runtime(self) -> CondaRuntime | None: ...

    def upgrade_pip(self, interpreter: Path, log: LineSink) -> None: ...
