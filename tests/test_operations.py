from __future__ import annotations

import json
import stat
from datetime import datetime
from pathlib import Path

import pytest

from envarium.core.errors import AppError, ErrorKind
from envarium.core.models import Environment, EnvKind, TerminalKind
from envarium.infrastructure.filesystem import (
    directory_metrics,
    metrics_signature,
    remove_tree,
)
from envarium.platforms.windows.operations import WindowsOperations


def make_environment(tmp_path: Path, kind: EnvKind, name: str = "env") -> Environment:
    path = tmp_path / name
    path.mkdir(parents=True)
    if kind is EnvKind.VENV:
        (path / "Scripts").mkdir()
        interpreter = path / "Scripts" / "python.exe"
    else:
        interpreter = path / "python.exe"
    interpreter.write_bytes(b"")
    return Environment(
        name=name, path=path, kind=kind, version="3.12.0", interpreter=interpreter
    )


def make_operations(tmp_path: Path, runner) -> tuple[WindowsOperations, Path]:
    conda = tmp_path / "miniconda3" / "Scripts" / "conda.exe"
    conda.parent.mkdir(parents=True, exist_ok=True)
    conda.write_bytes(b"")
    return WindowsOperations(runner, conda=conda), conda


def test_create_venv_invokes_module(tmp_path: Path, fake_runner) -> None:
    interpreter = tmp_path / "python.exe"
    target = tmp_path / "venvs" / "dev"
    runner = fake_runner({(str(interpreter), "-m", "venv", str(target)): ""})
    operations = WindowsOperations(runner)

    operations.create_venv(interpreter, target, system_site_packages=False)

    assert runner.calls == [(str(interpreter), "-m", "venv", str(target))]


def test_create_venv_with_system_site_packages(tmp_path: Path, fake_runner) -> None:
    interpreter = tmp_path / "python.exe"
    target = tmp_path / "dev"
    runner = fake_runner(
        {(str(interpreter), "-m", "venv", "--system-site-packages", str(target)): ""}
    )

    WindowsOperations(runner).create_venv(interpreter, target, system_site_packages=True)

    assert runner.calls[-1][3] == "--system-site-packages"


def test_create_venv_rejects_non_empty_target(tmp_path: Path, fake_runner) -> None:
    target = tmp_path / "dev"
    target.mkdir()
    (target / "existing.txt").write_text("occupied", encoding="utf-8")

    with pytest.raises(AppError) as error:
        WindowsOperations(fake_runner({})).create_venv(
            tmp_path / "python.exe", target, system_site_packages=False
        )

    assert error.value.kind is ErrorKind.INVALID


def test_create_conda_uses_name_and_version(tmp_path: Path, fake_runner) -> None:
    runner = fake_runner({})
    operations, conda = make_operations(tmp_path, runner)
    runner.responses[(str(conda), "create", "-y", "-n", "dev", "python=3.12")] = ""

    operations.create_conda("dev", "3.12")

    assert runner.calls == [(str(conda), "create", "-y", "-n", "dev", "python=3.12")]


def test_list_packages_parses_conda_json(tmp_path: Path, fake_runner) -> None:
    runner = fake_runner({})
    operations, conda = make_operations(tmp_path, runner)
    environment = make_environment(tmp_path, EnvKind.CONDA)
    runner.responses[
        (str(conda), "list", "-p", str(environment.path), "--json")
    ] = json.dumps([{"name": "numpy", "version": "2.0.0"}, {"name": "pip", "version": "24.0"}])

    packages = operations.list_packages(environment)

    assert [(package.name, package.version) for package in packages] == [
        ("numpy", "2.0.0"),
        ("pip", "24.0"),
    ]


def test_list_packages_parses_pip_json(tmp_path: Path, fake_runner) -> None:
    environment = make_environment(tmp_path, EnvKind.VENV)
    runner = fake_runner({})
    runner.responses[
        (str(environment.interpreter), "-m", "pip", "list", "--format=json")
    ] = json.dumps([{"name": "requests", "version": "2.32.0"}])

    packages = WindowsOperations(runner).list_packages(environment)

    assert [(package.name, package.version) for package in packages] == [
        ("requests", "2.32.0")
    ]


def test_install_uses_conda_for_conda_environment(tmp_path: Path, fake_runner) -> None:
    runner = fake_runner({})
    operations, conda = make_operations(tmp_path, runner)
    environment = make_environment(tmp_path, EnvKind.CONDA)
    lines: list[str] = []

    operations.install(environment, ["numpy", "pandas"], lines.append)

    assert runner.calls == [
        (str(conda), "install", "-y", "-p", str(environment.path), "numpy", "pandas")
    ]


def test_install_uses_pip_for_venv(tmp_path: Path, fake_runner) -> None:
    environment = make_environment(tmp_path, EnvKind.VENV)
    runner = fake_runner({})
    lines: list[str] = []

    WindowsOperations(runner).install(environment, ["requests"], lines.append)

    assert runner.calls == [
        (str(environment.interpreter), "-m", "pip", "install", "requests")
    ]


def test_install_failure_raises_app_error(tmp_path: Path, fake_runner) -> None:
    environment = make_environment(tmp_path, EnvKind.VENV)
    command = (str(environment.interpreter), "-m", "pip", "install", "broken")
    runner = fake_runner({}, stream_returncodes={command: 1})

    with pytest.raises(AppError) as error:
        WindowsOperations(runner).install(environment, ["broken"], lambda _line: None)

    assert error.value.kind is ErrorKind.COMMAND


def test_uninstall_uses_pip(tmp_path: Path, fake_runner) -> None:
    environment = make_environment(tmp_path, EnvKind.VENV)
    runner = fake_runner({})

    WindowsOperations(runner).uninstall(environment, "requests", lambda _line: None)

    assert runner.calls == [
        (str(environment.interpreter), "-m", "pip", "uninstall", "-y", "requests")
    ]


def test_remove_venv_deletes_directory(tmp_path: Path, fake_runner) -> None:
    environment = make_environment(tmp_path, EnvKind.VENV)

    WindowsOperations(fake_runner({})).remove(environment)

    assert not environment.path.exists()


def test_remove_conda_invokes_cli_and_cleans_leftovers(tmp_path: Path, fake_runner) -> None:
    runner = fake_runner({})
    operations, conda = make_operations(tmp_path, runner)
    environment = make_environment(tmp_path, EnvKind.CONDA)
    runner.responses[
        (str(conda), "env", "remove", "-y", "-p", str(environment.path))
    ] = ""

    operations.remove(environment)

    assert runner.calls == [
        (str(conda), "env", "remove", "-y", "-p", str(environment.path))
    ]
    assert not environment.path.exists()


def test_rename_venv_moves_directory(tmp_path: Path, fake_runner) -> None:
    environment = make_environment(tmp_path, EnvKind.VENV, name="old")

    WindowsOperations(fake_runner({})).rename(environment, "new")

    assert not environment.path.exists()
    assert (tmp_path / "new").is_dir()


def test_clone_uses_conda_clone(tmp_path: Path, fake_runner) -> None:
    runner = fake_runner({})
    operations, conda = make_operations(tmp_path, runner)
    environment = make_environment(tmp_path, EnvKind.CONDA)
    runner.responses[
        (
            str(conda),
            "create",
            "-y",
            "--clone",
            str(environment.path),
            "-n",
            "copy",
        )
    ] = ""

    operations.clone(environment, "copy")

    assert runner.calls[-1][3] == "--clone"


def test_activation_command_for_venv(tmp_path: Path, fake_runner) -> None:
    environment = make_environment(tmp_path, EnvKind.VENV)
    operations = WindowsOperations(fake_runner({}))

    powershell = operations.activation_command(environment, TerminalKind.POWERSHELL)
    cmd = operations.activation_command(environment, TerminalKind.CMD)

    assert powershell == f'& "{environment.path / "Scripts" / "Activate.ps1"}"'
    assert cmd == f'call "{environment.path / "Scripts" / "activate.bat"}"'


def test_activation_command_for_conda(tmp_path: Path, fake_runner) -> None:
    runner = fake_runner({})
    operations, conda = make_operations(tmp_path, runner)
    environment = make_environment(tmp_path, EnvKind.CONDA)

    powershell = operations.activation_command(environment, TerminalKind.POWERSHELL)
    cmd = operations.activation_command(environment, TerminalKind.CMD)

    assert "shell.powershell hook" in powershell
    assert f'conda activate "{environment.path}"' in powershell
    assert cmd == (
        f'call "{conda.parent.parent / "Scripts" / "activate.bat"}" "{environment.path}"'
    )


def test_directory_metrics_sums_nested_files(tmp_path: Path) -> None:
    nested = tmp_path / "Lib" / "site-packages"
    nested.mkdir(parents=True)
    (nested / "package.bin").write_bytes(b"x" * 120)
    (tmp_path / "root.bin").write_bytes(b"y" * 30)

    metrics = directory_metrics(tmp_path)

    assert metrics.size_bytes == 150
    assert metrics.writable
    assert metrics.modified_at > datetime(2000, 1, 1)


def test_remove_tree_reports_missing_path(tmp_path: Path) -> None:
    with pytest.raises(AppError) as error:
        remove_tree(tmp_path / "gone")

    assert error.value.kind is ErrorKind.NOT_FOUND


def test_remove_tree_clears_readonly_files(tmp_path: Path) -> None:
    target = tmp_path / "env"
    target.mkdir()
    readonly = target / "locked.txt"
    readonly.write_text("locked", encoding="utf-8")
    readonly.chmod(stat.S_IREAD)

    remove_tree(target)

    assert not target.exists()


def test_metrics_signature_changes_with_state_directory(tmp_path: Path) -> None:
    environment = tmp_path / "env"
    environment.mkdir()
    before = metrics_signature(environment)

    (environment / "Lib" / "site-packages").mkdir(parents=True)

    assert metrics_signature(environment) != before
