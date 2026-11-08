from __future__ import annotations

from pathlib import Path

from envarium.core.models import EnvKind
from envarium.platforms.windows.installations import discover_launcher_pythons


def test_discover_launcher_pythons_skips_missing_interpreters(tmp_path: Path, fake_runner) -> None:
    interpreter = tmp_path / "Python313" / "python.exe"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"")
    launcher = tmp_path / "py.exe"
    launcher.write_bytes(b"")
    output = (
        f" -V:3.13 *        {interpreter}\n"
        f" -V:3.11          {tmp_path / 'Python311' / 'python.exe'}\n"
    )
    runner = fake_runner({(str(launcher), "--list-paths"): output})

    environments = discover_launcher_pythons(runner, launcher)

    assert len(environments) == 1
    assert environments[0].kind is EnvKind.PYTHON
    assert environments[0].version == "3.13"
    assert environments[0].path == interpreter.parent


def test_discover_launcher_pythons_without_launcher(fake_runner) -> None:
    assert discover_launcher_pythons(fake_runner({}), launcher=None) == []
