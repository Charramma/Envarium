"""本地配置持久化：%LOCALAPPDATA%\\Envarium\\config.json。"""

from __future__ import annotations

import json
import logging
from enum import StrEnum
from pathlib import Path

from platformdirs import user_config_dir
from pydantic import BaseModel, ConfigDict, Field

from envarium.core.models import Environment, TerminalKind

logger = logging.getLogger(__name__)


class Theme(StrEnum):
    LIGHT = "light"
    DARK = "dark"


class AppConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    theme: Theme = Theme.LIGHT
    terminal: TerminalKind = TerminalKind.POWERSHELL
    manual_environments: list[Environment] = Field(default_factory=list)
    known_environments: list[Environment] = Field(default_factory=list)


class ConfigStore:
    """配置的唯一读写入口。"""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path(user_config_dir("Envarium", appauthor=False)) / "config.json"

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AppConfig:
        if not self._path.exists():
            return AppConfig()
        return AppConfig.model_validate_json(self._path.read_text(encoding="utf-8"))

    def save(self, config: AppConfig) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(config.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.debug("配置已保存：%s", self._path)
