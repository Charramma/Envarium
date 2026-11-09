"""环境库编排：发现、持久化、统计缓存与所有管理操作。"""

from __future__ import annotations

import itertools
import logging
import shutil
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from envarium.core.errors import AppError, ErrorKind, classify_os_error
from envarium.core.mirrors import Mirror
from envarium.core.models import (
    CondaChannel,
    Environment,
    EnvironmentMetrics,
    EnvKind,
    ExportFormat,
    PackageDiff,
    TerminalKind,
    normalize_path,
)
from envarium.core.ports import EnvironmentOperator, PlatformProvider
from envarium.infrastructure.config_store import ConfigStore
from envarium.infrastructure.filesystem import directory_metrics, metrics_signature
from envarium.services.export import render_export

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VenvRequest:
    """创建 venv 的输入。"""

    interpreter: Path
    target: Path
    system_site_packages: bool = False


@dataclass(frozen=True, slots=True)
class CondaRequest:
    """创建 conda 环境的输入。"""

    name: str
    python_version: str = ""
    channel: CondaChannel = CondaChannel.DEFAULTS


def merge_environments(groups: Iterable[Sequence[Environment]]) -> list[Environment]:
    """按来源优先级合并环境列表，同一路径上的环境以先出现者为准（conda 优先）。"""
    unique: dict[str, Environment] = {}
    for environment in itertools.chain.from_iterable(groups):
        unique.setdefault(environment.key, environment)
    return sorted(unique.values(), key=lambda environment: environment.name.lower())


class EnvironmentService:
    """对 UI 暴露的环境库唯一入口。"""

    def __init__(
        self,
        provider: PlatformProvider,
        operations: EnvironmentOperator,
        config_store: ConfigStore,
    ) -> None:
        self._provider = provider
        self._operations = operations
        self._config_store = config_store
        self._metrics: dict[str, tuple[tuple[int, ...], EnvironmentMetrics]] = {}

    def cached(self) -> list[Environment]:
        """上次刷新持久化的快照，用于秒开首屏。"""
        return self._annotate(merge_environments([self._config_store.load().known_environments]))

    def refresh(self) -> list[Environment]:
        """全量重新发现环境并写回快照，阻塞调用，应由后台任务执行。"""
        config = self._config_store.load()
        environments = self._annotate(
            merge_environments(
                [
                    self._provider.discover_conda_environments(),
                    self._provider.discover_installations(),
                    [self._refresh_manual(item) for item in config.manual_environments],
                ]
            )
        )
        self._config_store.save(config.model_copy(update={"known_environments": environments}))
        logger.info("环境刷新完成：%d 个", len(environments))
        return environments

    def create(self, request: VenvRequest | CondaRequest) -> Environment:
        """创建环境并立即纳入环境库。"""
        if isinstance(request, VenvRequest):
            self._operations.create_venv(
                request.interpreter,
                request.target,
                system_site_packages=request.system_site_packages,
            )
            self._remember_path(request.target)
            return self._require(self.refresh(), key=normalize_path(request.target))
        name = self._validate_name(request.name)
        self._operations.create_conda(name, request.python_version, request.channel)
        return self._require(self.refresh(), name=name)

    def conda_python_versions(self, channel: CondaChannel) -> list[str]:
        """列出频道当前可安装的 Python 版本，阻塞调用，应由后台任务执行。"""
        return self._operations.list_conda_python_versions(channel)

    def add_manual(self, path: Path) -> Environment:
        """把环境库之外的目录加入管理。"""
        environment = self._provider.inspect(path)
        if environment is None:
            raise AppError(f"该目录不是可识别的 Python 环境：{path}", kind=ErrorKind.INVALID)
        config = self._config_store.load()
        known = {
            item.key for item in (*config.manual_environments, *config.known_environments)
        }
        if environment.key in known:
            raise AppError(f"该环境已在环境库中：{environment.name}", kind=ErrorKind.INVALID)
        self._remember(environment)
        return self._require(self.refresh(), key=environment.key)

    def forget(self, environment: Environment) -> list[Environment]:
        """从环境库移除记录（用于清理已失效的路径）。"""
        self._forget(environment)
        return self.refresh()

    def remove(self, environment: Environment) -> None:
        if not environment.removable:
            raise AppError(
                "系统安装的 Python 与 conda base 环境不支持删除。", kind=ErrorKind.INVALID
            )
        self._operations.remove(environment)
        self._forget(environment)
        self._metrics.pop(environment.key, None)

    def rename(self, environment: Environment, new_name: str) -> Environment:
        if not environment.renamable:
            raise AppError("该环境不支持重命名。", kind=ErrorKind.INVALID)
        name = self._validate_name(new_name)
        new_path = environment.path.with_name(name)
        self._operations.rename(environment, name)
        self._forget(environment)
        if environment.kind is EnvKind.VENV:
            self._remember_path(new_path)
            return self._require(self.refresh(), key=normalize_path(new_path))
        return self._require(self.refresh(), name=name)

    def clone(self, environment: Environment, new_name: str) -> Environment:
        if not environment.cloneable:
            raise AppError("仅 conda 环境支持克隆。", kind=ErrorKind.INVALID)
        name = self._validate_name(new_name)
        self._operations.clone(environment, name)
        return self._require(self.refresh(), name=name)

    def export(
        self, environment: Environment, target: Path, export_format: ExportFormat
    ) -> Path:
        """按指定格式导出环境信息；阻塞调用，应由后台任务执行。"""
        content = render_export(
            environment,
            self._operations.list_packages(environment),
            self.metrics(environment),
            export_format,
        )
        try:
            target.write_text(content, encoding="utf-8")
        except OSError as error:
            raise classify_os_error(error, target) from error
        logger.info("已导出环境信息：%s -> %s", environment.name, target)
        return target

    def compare(self, left: Environment, right: Environment) -> list[PackageDiff]:
        """比较两个环境的包版本；阻塞调用，应由后台任务执行。"""
        left_packages = {
            package.name.lower(): package
            for package in self._operations.list_packages(left)
        }
        right_packages = {
            package.name.lower(): package
            for package in self._operations.list_packages(right)
        }
        return [
            PackageDiff(
                name=(left_packages.get(name) or right_packages[name]).name,
                left_version=(
                    left_packages[name].version if name in left_packages else ""
                ),
                right_version=(
                    right_packages[name].version if name in right_packages else ""
                ),
            )
            for name in sorted(left_packages.keys() | right_packages.keys())
        ]

    def metrics(self, environment: Environment) -> EnvironmentMetrics | None:
        """已计算且未过期的统计；过期或未计算时返回 None。"""
        cached = self._metrics.get(environment.key)
        if cached is None:
            return None
        signature, metrics = cached
        if signature != metrics_signature(environment.path):
            self._metrics.pop(environment.key, None)
            return None
        return metrics

    def measure(self, environments: Iterable[Environment]) -> dict[str, EnvironmentMetrics]:
        """计算并缓存环境统计，阻塞调用，应由后台任务执行。"""
        measured: dict[str, EnvironmentMetrics] = {}
        for environment in environments:
            metrics = self.metrics(environment)
            if metrics is None:
                if not environment.available or not environment.path.is_dir():
                    continue
                signature = metrics_signature(environment.path)
                metrics = directory_metrics(environment.path)
                self._metrics[environment.key] = (signature, metrics)
            measured[environment.key] = metrics
        return measured

    def open_terminal(self, environment: Environment, terminal: TerminalKind) -> None:
        self._operations.open_terminal(environment, terminal)

    def configure_mirror(self, mirror: Mirror) -> None:
        """写入用户级 pip / conda 镜像配置；阻塞调用，应由后台任务执行。"""
        self._operations.configure_mirror(mirror)

    def _annotate(self, environments: Sequence[Environment]) -> list[Environment]:
        """刷新由文件系统推导的运行时状态：是否可用、是否在当前 PATH 中。"""
        active = shutil.which("python")
        active_key = normalize_path(Path(active)) if active else ""
        return [
            environment.model_copy(
                update={
                    "available": environment.interpreter.is_file(),
                    "on_path": bool(active_key) and environment.key == active_key,
                }
            )
            for environment in environments
        ]

    def _refresh_manual(self, environment: Environment) -> Environment:
        if not environment.path.is_dir():
            return environment
        return self._provider.inspect(environment.path) or environment

    def _remember_path(self, path: Path) -> None:
        environment = self._provider.inspect(path)
        if environment is not None:
            self._remember(environment)

    def _remember(self, environment: Environment) -> None:
        config = self._config_store.load()
        manual = [item for item in config.manual_environments if item.key != environment.key]
        manual.append(environment)
        self._config_store.save(config.model_copy(update={"manual_environments": manual}))

    def _forget(self, environment: Environment) -> None:
        config = self._config_store.load()
        self._config_store.save(
            config.model_copy(
                update={
                    "manual_environments": [
                        item for item in config.manual_environments if item.key != environment.key
                    ],
                    "known_environments": [
                        item for item in config.known_environments if item.key != environment.key
                    ],
                }
            )
        )

    @staticmethod
    def _validate_name(new_name: str) -> str:
        name = new_name.strip()
        if not name or Path(name).name != name:
            raise AppError("名称不能为空，且不能包含路径分隔符。", kind=ErrorKind.INVALID)
        return name

    @staticmethod
    def _require(
        environments: Sequence[Environment],
        *,
        key: str | None = None,
        name: str | None = None,
    ) -> Environment:
        for environment in environments:
            if (key is not None and environment.key == key) or (
                name is not None and environment.name == name
            ):
                return environment
        raise AppError("操作已完成，但重新扫描时未发现该环境，请点击「刷新」后重试。")
