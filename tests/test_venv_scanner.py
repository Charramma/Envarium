from __future__ import annotations

from pathlib import Path

from envarium.core.models import EnvKind
from envarium.platforms.windows.venv_scanner import (
    read_pyvenv_cfg,
    read_venv_version,
    scan_virtualenvs,
)


def create_venv(path: Path, version: str = "3.13.5", with_interpreter: bool = True) -> Path:
    path.mkdir(parents=True)
    (path / "pyvenv.cfg").write_text(
        "home = C:\\Python313\n"
        "include-system-site-packages = false\n"
        f"version = {version}\n",
        encoding="utf-8",
    )
    if with_interpreter:
        scripts = path / "Scripts"
        scripts.mkdir()
        (scripts / "python.exe").write_bytes(b"")
    return path


def test_scan_finds_venv_at_root_and_nested(tmp_path: Path) -> None:
    create_venv(tmp_path / "project-a" / ".venv", version="3.12.1")
    create_venv(tmp_path / "project-b" / "envs" / "dev")

    found = scan_virtualenvs([tmp_path])

    assert {environment.name for environment in found} == {".venv", "dev"}
    assert all(environment.kind is EnvKind.VENV for environment in found)
    venv = next(environment for environment in found if environment.name == ".venv")
    assert venv.version == "3.12.1"


def test_scan_respects_depth_limit(tmp_path: Path) -> None:
    create_venv(tmp_path / "x" / "y" / "z")
    create_venv(tmp_path / "a" / "b" / "c" / "too-deep")

    found = scan_virtualenvs([tmp_path], max_depth=3)

    assert [environment.name for environment in found] == ["z"]


def test_scan_skips_venv_without_interpreter(tmp_path: Path) -> None:
    create_venv(tmp_path / "broken", with_interpreter=False)

    assert scan_virtualenvs([tmp_path]) == []


def test_scan_skips_noise_directories(tmp_path: Path) -> None:
    create_venv(tmp_path / "node_modules" / "lib" / ".venv")

    assert scan_virtualenvs([tmp_path]) == []


def test_scan_deduplicates_overlapping_roots(tmp_path: Path) -> None:
    create_venv(tmp_path / "project" / ".venv")

    found = scan_virtualenvs([tmp_path, tmp_path / "project"])

    assert len(found) == 1


def test_read_pyvenv_cfg(tmp_path: Path) -> None:
    cfg = create_venv(tmp_path / "venv", version="3.11.4") / "pyvenv.cfg"

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


def test_scan_reads_version_from_virtualenv_style_cfg(tmp_path: Path) -> None:
    venv = create_venv(tmp_path / "legacy")
    (venv / "pyvenv.cfg").write_text(
        "home = C:\\Python311\n"
        "version_info = 3.12.4.final.0\n"
        "virtualenv = 20.24.6\n",
        encoding="utf-8",
    )

    found = scan_virtualenvs([tmp_path])

    assert [environment.version for environment in found] == ["3.12.4"]
