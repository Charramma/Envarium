"""系统安装的 Python 解释器发现：PEP 514 注册表为主，py 启动器为辅。"""

from __future__ import annotations

import logging
import winreg
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from envarium.core.models import Environment, EnvKind, normalize_path
from envarium.infrastructure.subprocess_runner import SubprocessRunner

logger = logging.getLogger(__name__)

_PYTHON_KEY = r"Software\Python"
_HIVES = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
_VIEWS = (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)


@dataclass(frozen=True, slots=True)
class RegisteredPython:
    """PEP 514 注册表中的一条安装记录。"""

    display_name: str
    version: str
    install_path: Path
    executable: Path


def _read_value(key: int, name: str) -> str | None:
    try:
        value, _ = winreg.QueryValueEx(key, name)
    except OSError:
        return None
    return str(value)


def _subkey_names(hive: int, path: str, view: int) -> list[str]:
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ | view) as key:
            names: list[str] = []
            while True:
                try:
                    names.append(winreg.EnumKey(key, len(names)))
                except OSError:
                    return names
    except OSError:
        return []


def _read_install_path(key: int) -> tuple[Path, Path] | None:
    """PEP 514 把安装位置放在 InstallPath 子键：默认值为目录，ExecutablePath 为解释器。"""
    try:
        with winreg.OpenKey(key, "InstallPath") as install_key:
            install_dir = _read_value(install_key, "")
            executable = _read_value(install_key, "ExecutablePath")
    except OSError:
        return None
    if install_dir is None:
        return None
    install_path = Path(install_dir)
    return install_path, Path(executable) if executable else install_path / "python.exe"


def _read_registered_python(
    hive: int, view: int, company: str, tag: str
) -> RegisteredPython | None:
    path = f"{_PYTHON_KEY}\\{company}\\{tag}"
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ | view) as key:
            display_name = _read_value(key, "DisplayName") or f"Python {tag}"
            version = _read_value(key, "Version") or _read_value(key, "SysVersion") or tag
            install = _read_install_path(key)
    except OSError:
        return None
    if install is None:
        return None
    install_path, interpreter = install
    if not interpreter.is_file():
        return None
    return RegisteredPython(display_name, version, install_path, interpreter)


def _iter_registered_pythons() -> Iterator[RegisteredPython]:
    """遍历注册表中所有 32/64 位视图下的 Python 安装记录（按解释器去重）。"""
    seen: set[str] = set()
    for hive in _HIVES:
        for view in _VIEWS:
            for company in _subkey_names(hive, _PYTHON_KEY, view):
                company_path = f"{_PYTHON_KEY}\\{company}"
                for tag in _subkey_names(hive, company_path, view):
                    record = _read_registered_python(hive, view, company, tag)
                    if record is None:
                        continue
                    key = normalize_path(record.executable)
                    if key in seen:
                        continue
                    seen.add(key)
                    yield record


def discover_registered_pythons() -> list[Environment]:
    """注册表中登记的标准 Python 安装。"""
    return [
        Environment(
            name=record.display_name,
            path=record.install_path,
            kind=EnvKind.PYTHON,
            version=record.version,
            interpreter=record.executable,
        )
        for record in _iter_registered_pythons()
    ]


def discover_launcher_pythons(
    runner: SubprocessRunner, launcher: Path | None
) -> list[Environment]:
    """py 启动器登记的安装，用于补充未写入注册表的解释器。"""
    if launcher is None:
        return []
    result = runner.run([launcher, "--list-paths"])
    if not result.ok:
        logger.debug("py --list-paths 失败：%s", result.stderr.strip())
        return []

    environments: list[Environment] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2 or not parts[-1].lower().endswith(".exe"):
            continue
        interpreter = Path(parts[-1])
        raw_tag = parts[0].removeprefix("-V:")
        if raw_tag == parts[0] or not interpreter.is_file():
            continue
        tag = raw_tag.rsplit("/", 1)[-1]
        environments.append(
            Environment(
                name=f"Python {tag}",
                path=interpreter.parent,
                kind=EnvKind.PYTHON,
                version=tag.removeprefix("CPython"),
                interpreter=interpreter,
            )
        )
    return environments
