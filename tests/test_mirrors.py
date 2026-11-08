from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from envarium.core.mirrors import MIRRORS
from envarium.infrastructure.mirrors import write_conda_mirror, write_pip_mirror


def test_write_pip_mirror_preserves_other_settings(tmp_path: Path) -> None:
    path = tmp_path / "pip" / "pip.ini"
    path.parent.mkdir()
    path.write_text(
        "[global]\ntimeout = 30\nindex-url = https://old.example/simple\n", encoding="utf-8"
    )

    write_pip_mirror("https://mirror.example/simple", path)

    text = path.read_text(encoding="utf-8")
    assert "timeout = 30" in text
    assert "https://mirror.example/simple" in text
    assert "https://old.example/simple" not in text


def test_write_pip_mirror_restores_official_source(tmp_path: Path) -> None:
    path = tmp_path / "pip.ini"
    write_pip_mirror("https://mirror.example/simple", path)

    write_pip_mirror("", path)

    assert "index-url" not in path.read_text(encoding="utf-8")


def test_write_conda_mirror_adds_preset_channels(
    fake_runner: Callable[..., object],
) -> None:
    conda = Path("conda.exe")
    tsinghua = next(mirror for mirror in MIRRORS if mirror.key == "tsinghua")
    first, second = tsinghua.conda_channels
    runner = fake_runner(
        {
            ("conda.exe", "config", "--get", "channels"): "",
            ("conda.exe", "config", "--add", "channels", first): "",
            ("conda.exe", "config", "--add", "channels", second): "",
        }
    )

    write_conda_mirror(runner, conda, tsinghua.conda_channels)

    assert runner.calls == [
        ("conda.exe", "config", "--get", "channels"),
        ("conda.exe", "config", "--add", "channels", first),
        ("conda.exe", "config", "--add", "channels", second),
    ]


def test_write_conda_mirror_resets_existing_channels(
    fake_runner: Callable[..., object],
) -> None:
    runner = fake_runner(
        {
            ("conda.exe", "config", "--get", "channels"): "--add channels defaults",
            ("conda.exe", "config", "--remove-key", "channels"): "",
        }
    )

    write_conda_mirror(runner, Path("conda.exe"), ())

    assert ("conda.exe", "config", "--remove-key", "channels") in runner.calls
