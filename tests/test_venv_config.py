from __future__ import annotations

from pathlib import Path

from envarium.platforms.windows.venv_config import read_pyvenv_cfg, read_venv_version


def test_read_pyvenv_cfg(tmp_path: Path) -> None:
    cfg = tmp_path / "pyvenv.cfg"
    cfg.write_text(
        "home = C:\\Python313\n"
        "include-system-site-packages = false\n"
        "version = 3.11.4\n",
        encoding="utf-8",
    )

    values = read_pyvenv_cfg(cfg)

    assert values == {
        "home": "C:\\Python313",
        "include-system-site-packages": "false",
        "version": "3.11.4",
    }


def test_read_venv_version_prefers_version_key(tmp_path: Path) -> None:
    cfg = tmp_path / "pyvenv.cfg"
    cfg.write_text(
        "home = C:\\Python313\n"
        "version = 3.13.5\n"
        "version_info = 3.13.5.final.0\n",
        encoding="utf-8",
    )

    assert read_venv_version(cfg) == "3.13.5"


def test_read_venv_version_falls_back_to_version_info(tmp_path: Path) -> None:
    cfg = tmp_path / "pyvenv.cfg"
    cfg.write_text(
        "home = C:\\Python311\n"
        "implementation = CPython\n"
        "version_info = 3.11.5.final.0\n",
        encoding="utf-8",
    )

    assert read_venv_version(cfg) == "3.11.5"


def test_read_venv_version_returns_empty_without_version_fields(tmp_path: Path) -> None:
    cfg = tmp_path / "pyvenv.cfg"
    cfg.write_text("home = C:\\Python313\n", encoding="utf-8")

    assert read_venv_version(cfg) == ""
