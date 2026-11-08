"""文件系统采集与目录变更：统计环境占用、删除与重命名目录。"""

from __future__ import annotations

import logging
import os
import shutil
import stat
from datetime import datetime
from pathlib import Path

from envarium.core.errors import AppError, ErrorKind, classify_os_error
from envarium.core.models import EnvironmentMetrics

logger = logging.getLogger(__name__)

# 站点包与元数据目录的时间戳能反映环境内容是否变化，用于校验统计缓存
_STATE_CANDIDATES = ("Lib/site-packages", "conda-meta")


def metrics_signature(path: Path) -> tuple[int, ...]:
    """统计缓存的轻量校验值：环境根目录与内容目录的修改时间。"""
    stamps = [path]
    stamps.extend(path / candidate for candidate in _STATE_CANDIDATES)
    values: list[int] = []
    for candidate in stamps:
        try:
            values.append(candidate.stat().st_mtime_ns)
        except OSError:
            values.append(0)
    return tuple(values)


def directory_metrics(path: Path) -> EnvironmentMetrics:
    """遍历目录，累计文件大小并取最近修改时间。"""
    total = 0
    latest = 0.0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            logger.debug("目录不可访问：%s", current)
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            total += entry_stat.st_size
            latest = max(latest, entry_stat.st_mtime)

    if latest == 0.0:
        try:
            latest = path.stat().st_mtime
        except OSError:
            latest = 0.0
    return EnvironmentMetrics(
        size_bytes=total,
        modified_at=datetime.fromtimestamp(latest),
        writable=os.access(path, os.W_OK),
    )


def _retry_writable(function, target: str, _error: tuple[type, BaseException, object]) -> None:
    """Windows 上只读文件的删除先去掉只读属性再试一次。"""
    os.chmod(target, stat.S_IWRITE)
    function(target)


def remove_tree(path: Path) -> None:
    """删除环境目录，失败时按错误类型给出可操作提示。"""
    if not path.exists():
        raise AppError(f"环境路径不存在：{path}", kind=ErrorKind.NOT_FOUND)
    try:
        shutil.rmtree(path, onerror=_retry_writable)
    except OSError as error:
        raise classify_os_error(error, path) from error
    logger.info("已删除目录：%s", path)


def rename_directory(source: Path, target: Path) -> None:
    """在同一父目录内重命名环境目录。"""
    if target.exists():
        raise AppError(f"目标目录已存在：{target}", kind=ErrorKind.INVALID)
    try:
        source.rename(target)
    except OSError as error:
        raise classify_os_error(error, source) from error
    logger.info("已重命名目录：%s -> %s", source, target)
