"""镜像源落盘：用户级 pip.ini 与 conda channels。"""

from __future__ import annotations

import configparser
import os
from collections.abc import Iterable
from pathlib import Path

from envarium.core.errors import AppError
from envarium.infrastructure.subprocess_runner import CommandResult, SubprocessRunner

PIP_INI = (
    Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "pip" / "pip.ini"
)


def write_pip_mirror(index_url: str, path: Path = PIP_INI) -> None:
    """把 pip 源写入用户级 pip.ini，空地址表示恢复官方源。"""
    parser = configparser.ConfigParser()
    if path.is_file():
        parser.read(path, encoding="utf-8")
    if not parser.has_section("global"):
        parser.add_section("global")
    if index_url:
        parser.set("global", "index-url", index_url)
    else:
        parser.remove_option("global", "index-url")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        parser.write(handle)


def write_conda_mirror(
    runner: SubprocessRunner, conda: Path, channels: Iterable[str]
) -> None:
    """重置 conda channels 为指定镜像；空列表表示恢复默认。"""
    existing = runner.run([conda, "config", "--get", "channels"])
    if existing.ok and existing.stdout.strip():
        _check(runner.run([conda, "config", "--remove-key", "channels"]))
    for channel in channels:
        _check(runner.run([conda, "config", "--add", "channels", channel]))


def _check(result: CommandResult) -> None:
    if result.ok:
        return
    detail = (result.stderr or result.stdout).strip()
    raise AppError(f"conda 配置命令失败（返回码 {result.returncode}）", detail=detail[-1000:])
