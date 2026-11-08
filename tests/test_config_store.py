from __future__ import annotations

from pathlib import Path

from envarium.core.models import Environment, EnvKind
from envarium.infrastructure.config_store import AppConfig, ConfigStore, Theme


def test_missing_config_returns_defaults(tmp_path: Path) -> None:
    config = ConfigStore(tmp_path / "config.json").load()

    assert config == AppConfig()


def test_config_roundtrip(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "nested" / "config.json")
    environment = Environment(
        name="dev",
        path=tmp_path / "dev",
        kind=EnvKind.VENV,
        version="3.13.5",
        interpreter=tmp_path / "dev" / "Scripts" / "python.exe",
    )
    store.save(
        AppConfig(
            theme=Theme.DARK,
            venv_scan_roots=[tmp_path],
            known_environments=[environment],
        )
    )

    loaded = store.load()

    assert loaded.theme is Theme.DARK
    assert loaded.venv_scan_roots == [tmp_path]
    assert loaded.known_environments == [environment]
