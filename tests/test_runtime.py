from __future__ import annotations

from pathlib import Path

import pytest

from envarium.core.errors import AppError
from envarium.core.models import Environment, EnvKind
from envarium.platforms.windows.runtime import (
    WindowsRuntimeProbe,
    describe_system,
    parse_conda_version,
    parse_pip_version,
)


def make_environment(tmp_path: Path, kind: EnvKind) -> Environment:
    path = tmp_path / kind.value
    path.mkdir(parents=True)
    interpreter = path / "python.exe"
    interpreter.write_bytes(b"")
    return Environment(
        name=kind.value, path=path, kind=kind, version="3.13.5", interpreter=interpreter
    )


def test_describe_system_reports_windows_11_for_new_build() -> None:
    info = describe_system("Windows", "10", "10.0.22631", "AMD64")

    assert info.release == "11"
    assert info.machine == "x64"
    assert info.display == "Windows 11 / x64"


def test_describe_system_keeps_windows_10_and_maps_architecture() -> None:
    info = describe_system("Windows", "10", "10.0.19045", "ARM64")

    assert info.release == "10"
    assert info.machine == "arm64"
    assert info.display == "Windows 10 / arm64"


def test_parse_pip_version_reads_version_and_location() -> None:
    version, path = parse_pip_version(
        "pip 25.2 from C:\\Python313\\Lib\\site-packages\\pip (python 3.13)"
    )

    assert version == "25.2"
    assert path == Path("C:\\Python313\\Lib\\site-packages\\pip")


def test_parse_pip_version_returns_empty_for_unexpected_output() -> None:
    assert parse_pip_version("No module named pip") == ("", None)


def test_parse_conda_version_reads_version() -> None:
    assert parse_conda_version("conda 24.9.2\n") == "24.9.2"


def test_python_toolchains_only_queries_system_installations(tmp_path: Path, fake_runner) -> None:
    python = make_environment(tmp_path, EnvKind.PYTHON)
    venv = make_environment(tmp_path, EnvKind.VENV)
    runner = fake_runner(
        {
            (str(python.interpreter), "-m", "pip", "--version"): (
                "pip 25.2 from C:\\Python313\\Lib\\site-packages\\pip (python 3.13)"
            )
        }
    )

    toolchains = WindowsRuntimeProbe(runner).python_toolchains([python, venv])

    assert [toolchain.environment.name for toolchain in toolchains] == ["python"]
    assert toolchains[0].pip_version == "25.2"
    assert runner.calls == [(str(python.interpreter), "-m", "pip", "--version")]


def test_conda_runtime_reads_version(tmp_path: Path, fake_runner) -> None:
    conda = tmp_path / "miniconda3" / "Scripts" / "conda.exe"
    conda.parent.mkdir(parents=True)
    conda.write_bytes(b"")
    runner = fake_runner({(str(conda), "--version"): "conda 24.9.2\n"})

    runtime = WindowsRuntimeProbe(runner, conda=conda).conda_runtime()

    assert runtime is not None
    assert runtime.version == "24.9.2"
    assert runtime.executable == conda


def test_upgrade_pip_raises_when_command_fails(tmp_path: Path, fake_runner) -> None:
    interpreter = tmp_path / "python.exe"
    interpreter.write_bytes(b"")
    runner = fake_runner(
        stream_returncodes={
            (str(interpreter), "-m", "pip", "install", "--upgrade", "pip"): 1
        }
    )

    with pytest.raises(AppError):
        WindowsRuntimeProbe(runner).upgrade_pip(interpreter, lambda _line: None)
