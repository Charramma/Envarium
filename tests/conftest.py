"""测试共享的假子进程执行器。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from envarium.infrastructure.subprocess_runner import CommandResult


class FakeRunner:
    """按命令返回预置 stdout；只替换最外层的子进程边界。"""

    def __init__(self, responses: dict[tuple[str, ...], str]) -> None:
        self._responses = responses

    def run(self, command, *, cwd: Path | None = None) -> CommandResult:
        args = tuple(str(part) for part in command)
        return CommandResult(args, 0, self._responses[args], "")


@pytest.fixture
def fake_runner() -> Callable[[dict[tuple[str, ...], str]], FakeRunner]:
    return FakeRunner
