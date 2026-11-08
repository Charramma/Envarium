"""环境库编排：合并多来源、去重、缓存快照。"""

from __future__ import annotations

import itertools
import logging
from collections.abc import Iterable, Sequence

from envarium.core.models import Environment, dedupe_environments
from envarium.core.ports import PlatformProvider
from envarium.infrastructure.config_store import ConfigStore

logger = logging.getLogger(__name__)


def merge_environments(groups: Iterable[Sequence[Environment]]) -> list[Environment]:
    """按来源优先级合并环境列表，同一路径上的环境以先出现者为准（conda 优先）。"""
    merged = dedupe_environments(itertools.chain.from_iterable(groups))
    return sorted(merged, key=lambda environment: environment.name.lower())


class EnvironmentService:
    """对 UI 暴露的环境库唯一入口。"""

    def __init__(self, provider: PlatformProvider, config_store: ConfigStore) -> None:
        self._provider = provider
        self._config_store = config_store

    def cached(self) -> list[Environment]:
        """上次刷新持久化的快照，用于秒开首屏。"""
        return merge_environments([self._config_store.load().known_environments])

    def refresh(self) -> list[Environment]:
        """全量重新发现环境并写回快照，阻塞调用，应由后台任务执行。"""
        config = self._config_store.load()
        environments = merge_environments(
            [
                self._provider.discover_conda_environments(),
                self._provider.scan_virtualenvs(config.venv_scan_roots),
                self._provider.discover_installations(),
            ]
        )
        self._config_store.save(config.model_copy(update={"known_environments": environments}))
        logger.info("环境刷新完成：%d 个", len(environments))
        return environments
