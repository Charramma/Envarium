"""日志初始化：文件 + 控制台。"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_log_dir

_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def log_directory() -> Path:
    """日志目录（不存在时创建）。"""
    return Path(user_log_dir("Envarium", ensure_exists=True))


def configure_logging(level: int = logging.INFO) -> None:
    """配置根日志器：滚动文件 + 标准错误。"""
    log_file = log_directory() / "envarium.log"
    formatter = logging.Formatter(_LOG_FORMAT)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
