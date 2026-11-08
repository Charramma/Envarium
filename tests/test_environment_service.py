from __future__ import annotations

from pathlib import Path

from envarium.core.models import Environment, EnvKind
from envarium.infrastructure.config_store import AppConfig, ConfigStore
from envarium.services.environment_service import EnvironmentService, merge_environments


def make_environment(path: Path, kind: EnvKind, name: str, version: str = "3.12.0") -> Environment:
    return Environment(
        name=name,
        path=path,
        kind=kind,
        version=version,
        interpreter=path / "python.exe",
    )


class StubProvider:
    def __init__(
        self,
        installations: list[Environment],
        conda: list[Environment],
        virtualenvs: list[Environment],
    ) -> None:
        self._installations = installations
        self._conda = conda
        self._virtualenvs = virtualenvs
        self.requested_roots: list[Path] = []

    def discover_installations(self) -> list[Environment]:
        return self._installations

    def discover_conda_environments(self) -> list[Environment]:
        return self._conda

    def scan_virtualenvs(self, roots: list[Path]) -> list[Environment]:
        self.requested_roots = list(roots)
        return self._virtualenvs


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


def test_refresh_persists_snapshot_and_scans_configured_roots(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    install_root = tmp_path / "Python313"
    conda_root = tmp_path / "miniconda3"
    venv_root = tmp_path / "project" / ".venv"
    provider = StubProvider(
        installations=[make_environment(install_root, EnvKind.PYTHON, "Python 3.13")],
        conda=[make_environment(conda_root, EnvKind.CONDA, "base")],
        virtualenvs=[make_environment(venv_root, EnvKind.VENV, ".venv")],
    )
    store.save(AppConfig(venv_scan_roots=[tmp_path / "project"]))
    service = EnvironmentService(provider, store)

    refreshed = service.refresh()

    assert provider.requested_roots == [tmp_path / "project"]
    assert {environment.name for environment in refreshed} == {"Python 3.13", "base", ".venv"}
    assert [environment.name for environment in service.cached()] == [
        environment.name for environment in refreshed
    ]


def test_cached_returns_last_snapshot(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    stub = make_environment(tmp_path / "env", EnvKind.VENV, "cached-env")
    store.save(AppConfig(known_environments=[stub]))
    service = EnvironmentService(StubProvider([], [], []), store)

    assert [environment.name for environment in service.cached()] == ["cached-env"]
