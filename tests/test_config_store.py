from __future__ import annotations

from pathlib import Path

from envarium.core.models import Environment, EnvKind, TerminalKind
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
            terminal=TerminalKind.CMD,
            venv_scan_roots=[tmp_path],
            manual_environments=[environment],
            known_environments=[environment],
        )
    )

    loaded = store.load()

    assert loaded.theme is Theme.DARK
    assert loaded.terminal is TerminalKind.CMD
    assert loaded.venv_scan_roots == [tmp_path]
    assert loaded.manual_environments == [environment]
    assert loaded.known_environments == [environment]
