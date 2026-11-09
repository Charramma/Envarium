"""解析 venv 的 pyvenv.cfg，获取其 Python 版本。"""

from __future__ import annotations

from pathlib import Path


def read_pyvenv_cfg(cfg_path: Path) -> dict[str, str]:
    """解析 pyvenv.cfg 的 key = value 结构。"""
    values: dict[str, str] = {}
    for line in cfg_path.read_text(encoding="utf-8", errors="replace").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip()
    return values


def read_venv_version(cfg_path: Path) -> str:
    """读取 venv 的 Python 版本；兼容 virtualenv 只写 version_info 的格式。"""
    values = read_pyvenv_cfg(cfg_path)
    version = values.get("version", "")
    if version:
        return version
    # version_info 形如 3.11.5.final.0，取前三段
    return ".".join(values.get("version_info", "").split(".")[:3])
