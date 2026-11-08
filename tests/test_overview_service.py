from __future__ import annotations

from pathlib import Path

from envarium.core.models import (
    CondaRuntime,
    Environment,
    EnvKind,
    PythonToolchain,
    SystemInfo,
)
from envarium.services.overview_service import OverviewService

SYSTEM = SystemInfo(
    name="Windows",
    release="11",
    version="10.0.22631",
    machine="x64",
    display="Windows 11 / x64",
)


class FakeProbe:
    def __init__(self) -> None:
        self.toolchain_inputs: list[list[Environment]] = []
        self.upgraded: list[Path] = []

    def system_info(self) -> SystemInfo:
        return SYSTEM

    def python_toolchains(
        self, installations: list[Environment]
    ) -> list[PythonToolchain]:
        self.toolchain_inputs.append(list(installations))
        return [PythonToolchain(environment=item) for item in installations]

    def conda_runtime(self) -> CondaRuntime | None:
        return CondaRuntime(executable=Path("C:/miniconda3/conda.exe"), version="24.9.2")

    def upgrade_pip(self, interpreter: Path, log) -> None:
        log("upgrading")
        self.upgraded.append(interpreter)


def make_environment(tmp_path: Path, kind: EnvKind, name: str) -> Environment:
    path = tmp_path / name
    path.mkdir(parents=True)
    return Environment(
        name=name, path=path, kind=kind, version="3.12.0", interpreter=path / "python.exe"
    )


def test_snapshot_partitions_environments_by_kind(tmp_path: Path) -> None:
    probe = FakeProbe()
    service = OverviewService(probe)
    python = make_environment(tmp_path, EnvKind.PYTHON, "Python313")
    venv = make_environment(tmp_path, EnvKind.VENV, "dev")
    conda = make_environment(tmp_path, EnvKind.CONDA, "base")

    data = service.snapshot([python, venv, conda])

    assert [item.name for item in data.venvs] == ["dev"]
    assert [item.name for item in data.conda_environments] == ["base"]
    assert [item.environment.name for item in data.pythons] == ["Python313"]
    assert data.system == SYSTEM
    assert data.conda is not None and data.conda.version == "24.9.2"
    assert probe.toolchain_inputs == [[python]]


def test_upgrade_pip_delegates_to_probe_with_interpreter(tmp_path: Path) -> None:
    probe = FakeProbe()
    service = OverviewService(probe)
    environment = make_environment(tmp_path, EnvKind.PYTHON, "Python313")
    toolchain = PythonToolchain(environment=environment)
    lines: list[str] = []

    service.upgrade_pip(toolchain, lines.append)

    assert probe.upgraded == [environment.interpreter]
    assert lines == ["upgrading"]
