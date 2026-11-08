"""包管理编排：列表、安装与卸载。"""

from __future__ import annotations

from collections.abc import Sequence

from envarium.core.models import Environment, Package
from envarium.core.ports import EnvironmentOperator, LineSink


class PackageService:
    """对 UI 暴露的包管理唯一入口。"""

    def __init__(self, operations: EnvironmentOperator) -> None:
        self._operations = operations

    def list(self, environment: Environment) -> list[Package]:
        packages = self._operations.list_packages(environment)
        return sorted(packages, key=lambda package: package.name.lower())

    def install(self, environment: Environment, specs: Sequence[str], log: LineSink) -> None:
        self._operations.install(environment, specs, log)

    def uninstall(self, environment: Environment, name: str, log: LineSink) -> None:
        self._operations.uninstall(environment, name, log)
