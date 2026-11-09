from __future__ import annotations

import json
from pathlib import Path

import pytest

from envarium.core.errors import AppError, ErrorKind
from envarium.core.models import Environment, EnvKind, ExportFormat, Package
from envarium.infrastructure.config_store import AppConfig, ConfigStore
from envarium.services.environment_service import (
    CondaRequest,
    EnvironmentService,
    VenvRequest,
    merge_environments,
)


def make_environment(path: Path, kind: EnvKind, name: str, version: str = "3.12.0") -> Environment:
    return Environment(
        name=name,
        path=path,
        kind=kind,
        version=version,
        interpreter=path / "python.exe",
    )


def create_real_environment(root: Path, kind: EnvKind, name: str) -> Environment:
    path = root / name
    path.mkdir(parents=True)
    if kind is EnvKind.VENV:
        (path / "Scripts").mkdir()
        interpreter = path / "Scripts" / "python.exe"
    else:
        interpreter = path / "python.exe"
    interpreter.write_bytes(b"")
    (path / "payload.bin").write_bytes(b"x" * 64)
    return Environment(name=name, path=path, kind=kind, version="3.12.0", interpreter=interpreter)


class StubProvider:
    def __init__(
        self,
        installations: list[Environment] | None = None,
        conda: list[Environment] | None = None,
        inspected: dict[str, Environment] | None = None,
    ) -> None:
        self._installations = installations or []
        self._conda = conda or []
        self._inspected = inspected or {}

    def discover_installations(self) -> list[Environment]:
        return self._installations

    def discover_conda_environments(self) -> list[Environment]:
        return self._conda

    def inspect(self, path: Path) -> Environment | None:
        return self._inspected.get(str(path))


class StubOperations:
    def __init__(self, packages: dict[str, list[Package]] | None = None) -> None:
        self.created_venv: tuple[Path, Path, bool] | None = None
        self.removed: Environment | None = None
        self._packages = packages or {}

    def create_venv(self, interpreter: Path, target: Path, *, system_site_packages: bool) -> None:
        self.created_venv = (interpreter, target, system_site_packages)

    def remove(self, environment: Environment) -> None:
        self.removed = environment

    def list_packages(self, environment: Environment) -> list[Package]:
        return self._packages.get(environment.key, [])


def test_merge_prefers_conda_over_other_sources(tmp_path: Path) -> None:
    shared = tmp_path / "miniconda3"
    conda = make_environment(shared, EnvKind.CONDA, "base")
    installed = make_environment(shared, EnvKind.PYTHON, "Python 3.12")

    merged = merge_environments([[conda], [], [installed]])

    assert len(merged) == 1
    assert merged[0].kind is EnvKind.CONDA


def test_merge_sorts_by_name(tmp_path: Path) -> None:
    zulu = make_environment(tmp_path / "zulu", EnvKind.VENV, "zulu")
    alpha = make_environment(tmp_path / "alpha", EnvKind.VENV, "alpha")

    merged = merge_environments([[zulu, alpha]])

    assert [environment.name for environment in merged] == ["alpha", "zulu"]


def test_refresh_persists_snapshot(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    install_root = tmp_path / "Python313"
    conda_root = tmp_path / "miniconda3"
    provider = StubProvider(
        installations=[make_environment(install_root, EnvKind.PYTHON, "Python 3.13")],
        conda=[make_environment(conda_root, EnvKind.CONDA, "base")],
    )
    service = EnvironmentService(provider, StubOperations(), store)

    refreshed = service.refresh()

    assert {environment.name for environment in refreshed} == {"Python 3.13", "base"}
    assert [environment.name for environment in service.cached()] == [
        environment.name for environment in refreshed
    ]


def test_cached_returns_last_snapshot(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    stub = make_environment(tmp_path / "env", EnvKind.VENV, "cached-env")
    store.save(AppConfig(known_environments=[stub]))
    service = EnvironmentService(StubProvider(), StubOperations(), store)

    assert [environment.name for environment in service.cached()] == ["cached-env"]


def test_manual_environment_marks_missing_path_as_unavailable(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    missing = make_environment(tmp_path / "gone", EnvKind.VENV, "gone")
    store.save(AppConfig(manual_environments=[missing]))
    service = EnvironmentService(StubProvider(), StubOperations(), store)

    refreshed = service.refresh()

    assert [environment.name for environment in refreshed] == ["gone"]
    assert refreshed[0].available is False


def test_add_manual_persists_and_validates(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    real = create_real_environment(tmp_path, EnvKind.VENV, "dev")
    provider = StubProvider(inspected={str(real.path): real})
    service = EnvironmentService(provider, StubOperations(), store)

    added = service.add_manual(real.path)

    assert added.key == real.key
    assert store.load().manual_environments[0].key == real.key
    with pytest.raises(AppError) as error:
        service.add_manual(tmp_path / "unknown")
    assert error.value.kind is ErrorKind.INVALID
    assert error.value.message.startswith("该目录不是可识别的")


def test_add_manual_rejects_environment_already_known(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    real = create_real_environment(tmp_path, EnvKind.VENV, "dev")
    store.save(AppConfig(known_environments=[real]))
    service = EnvironmentService(
        StubProvider(inspected={str(real.path): real}), StubOperations(), store
    )

    with pytest.raises(AppError) as error:
        service.add_manual(real.path)

    assert error.value.kind is ErrorKind.INVALID


def test_create_venv_remembers_environment(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    target = tmp_path / "venvs" / "dev"
    created = create_real_environment(tmp_path / "venvs", EnvKind.VENV, "dev")
    provider = StubProvider(inspected={str(target): created})
    operations = StubOperations()
    service = EnvironmentService(provider, operations, store)

    result = service.create(VenvRequest(tmp_path / "python.exe", target))

    assert operations.created_venv == (tmp_path / "python.exe", target, False)
    assert result.key == created.key
    assert store.load().manual_environments[0].key == created.key


def test_create_conda_validates_name(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    service = EnvironmentService(StubProvider(), StubOperations(), store)

    with pytest.raises(AppError) as error:
        service.create(CondaRequest("bad/name", "3.12"))

    assert error.value.kind is ErrorKind.INVALID


def test_remove_rejects_system_python(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    operations = StubOperations()
    service = EnvironmentService(StubProvider(), operations, store)
    installed = make_environment(tmp_path / "Python313", EnvKind.PYTHON, "Python 3.13")

    with pytest.raises(AppError) as error:
        service.remove(installed)

    assert error.value.kind is ErrorKind.INVALID
    assert operations.removed is None


def test_measure_caches_metrics_until_environment_disappears(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    environment = create_real_environment(tmp_path, EnvKind.VENV, "dev")
    service = EnvironmentService(StubProvider(), StubOperations(), store)

    measured = service.measure([environment])

    assert measured[environment.key].size_bytes == 64
    assert service.metrics(environment) is not None
    environment.path.rename(tmp_path / "moved")
    assert service.metrics(environment) is None


def test_forget_removes_invalid_record(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    missing = make_environment(tmp_path / "gone", EnvKind.VENV, "gone")
    store.save(AppConfig(manual_environments=[missing], known_environments=[missing]))
    service = EnvironmentService(StubProvider(), StubOperations(), store)

    remaining = service.forget(missing)

    assert remaining == []
    assert store.load().manual_environments == []


def test_export_requirements_lists_pinned_packages(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    environment = create_real_environment(tmp_path, EnvKind.VENV, "dev")
    operations = StubOperations(
        {
            environment.key: [
                Package(name="numpy", version="2.1.3"),
                Package(name="pip", version="24.0"),
            ]
        }
    )
    service = EnvironmentService(StubProvider(), operations, store)

    target = service.export(
        environment, tmp_path / "requirements.txt", ExportFormat.REQUIREMENTS
    )

    assert target.read_text(encoding="utf-8") == "numpy==2.1.3\npip==24.0\n"


def test_export_environment_yml_requires_conda(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    environment = create_real_environment(tmp_path, EnvKind.VENV, "dev")
    service = EnvironmentService(StubProvider(), StubOperations(), store)

    with pytest.raises(AppError) as error:
        service.export(environment, tmp_path / "environment.yml", ExportFormat.CONDA_ENV)

    assert error.value.kind is ErrorKind.INVALID


def test_export_environment_yml_contains_python_and_packages(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    environment = create_real_environment(tmp_path, EnvKind.CONDA, "ml")
    operations = StubOperations(
        {
            environment.key: [
                Package(name="python", version="3.12.0"),
                Package(name="numpy", version="2.1.3"),
            ]
        }
    )
    service = EnvironmentService(StubProvider(), operations, store)

    target = service.export(
        environment, tmp_path / "environment.yml", ExportFormat.CONDA_ENV
    )

    lines = target.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "name: ml"
    assert "  - python=3.12.0" in lines
    assert "  - numpy=2.1.3" in lines


def test_export_json_snapshot_contains_environment_and_packages(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    environment = create_real_environment(tmp_path, EnvKind.VENV, "dev")
    operations = StubOperations(
        {environment.key: [Package(name="requests", version="2.32.0")]}
    )
    service = EnvironmentService(StubProvider(), operations, store)

    target = service.export(environment, tmp_path / "snapshot.json", ExportFormat.JSON)

    snapshot = json.loads(target.read_text(encoding="utf-8"))
    assert snapshot["environment"]["name"] == "dev"
    assert snapshot["packages"] == [{"name": "requests", "version": "2.32.0"}]


def test_compare_reports_differences_in_both_directions(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    left = create_real_environment(tmp_path, EnvKind.VENV, "left")
    right = create_real_environment(tmp_path, EnvKind.VENV, "right")
    operations = StubOperations(
        {
            left.key: [
                Package(name="numpy", version="2.0.0"),
                Package(name="only-left", version="1.0"),
            ],
            right.key: [
                Package(name="numpy", version="2.1.3"),
                Package(name="only-right", version="1.0"),
            ],
        }
    )
    service = EnvironmentService(StubProvider(), operations, store)

    diffs = {diff.name: diff for diff in service.compare(left, right)}

    assert diffs["numpy"].differs is True
    assert (diffs["numpy"].left_version, diffs["numpy"].right_version) == ("2.0.0", "2.1.3")
    assert diffs["only-left"].right_version == ""
    assert diffs["only-right"].left_version == ""
