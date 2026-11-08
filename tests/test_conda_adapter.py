from __future__ import annotations

import json
from pathlib import Path

from envarium.platforms.windows import conda_adapter
from envarium.platforms.windows.conda_adapter import (
    find_conda,
    list_conda_environments,
    read_conda_python_version,
)


def create_conda_env(path: Path, version: str) -> Path:
    path.mkdir(parents=True)
    (path / "python.exe").write_bytes(b"")
    meta = path / "conda-meta"
    meta.mkdir()
    (meta / f"python-{version}-h1234_0.json").write_text("{}", encoding="utf-8")
    return path


def create_conda_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def test_find_conda_prefers_native_exe_over_bat_wrapper(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "anaconda3"
    wrapper = create_conda_executable(root / "Library" / "bin" / "conda.bat")
    native = create_conda_executable(root / "Scripts" / "conda.exe")
    monkeypatch.setattr(conda_adapter.shutil, "which", lambda name: str(wrapper))

    assert find_conda() == native


def test_list_conda_environments(tmp_path: Path, fake_runner) -> None:
    base = create_conda_env(tmp_path / "miniconda3", "3.12.4")
    data = create_conda_env(tmp_path / "envs" / "data", "3.11.9")
    executable = create_conda_executable(tmp_path / "miniconda3" / "Scripts" / "conda.exe")
    runner = fake_runner(
        {
            (str(executable), "env", "list", "--json"): json.dumps(
                {"envs": [str(base), str(data)]}
            ),
            (str(executable), "info", "--json"): json.dumps({"root_prefix": str(base)}),
        }
    )

    environments = list_conda_environments(runner, executable)

    assert [environment.name for environment in environments] == ["base", "data"]
    assert environments[0].is_base
    assert not environments[1].is_base
    assert environments[1].version == "3.11.9"


def test_list_conda_environments_skips_missing_interpreter(tmp_path: Path, fake_runner) -> None:
    base = create_conda_env(tmp_path / "miniconda3", "3.12.4")
    ghost = tmp_path / "envs" / "ghost"
    ghost.mkdir(parents=True)
    executable = create_conda_executable(tmp_path / "miniconda3" / "Scripts" / "conda.exe")
    runner = fake_runner(
        {
            (str(executable), "env", "list", "--json"): json.dumps(
                {"envs": [str(base), str(ghost)]}
            ),
            (str(executable), "info", "--json"): json.dumps({}),
        }
    )

    environments = list_conda_environments(runner, executable)

    assert [environment.name for environment in environments] == ["miniconda3"]
    assert not environments[0].is_base


def test_read_conda_python_version_ignores_unrelated_packages(tmp_path: Path) -> None:
    environment = create_conda_env(tmp_path / "env", "3.10.13")
    (environment / "conda-meta" / "python-dateutil-2.9.0-pyhd8ed1ab_0.json").write_text(
        "{}", encoding="utf-8"
    )

    assert read_conda_python_version(environment) == "3.10.13"


def test_read_conda_python_version_without_metadata(tmp_path: Path) -> None:
    assert read_conda_python_version(tmp_path / "nothing") == ""
