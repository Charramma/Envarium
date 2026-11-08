"""测试共享的假子进程执行器。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from envarium.infrastructure.subprocess_runner import CommandResult


class FakeRunner:
    """按命令返回预置输出，并记录实际执行的命令。只替换最外层的子进程边界。"""

    def __init__(
        self,
        responses: dict[tuple[str, ...], str] | None = None,
        *,
        returncodes: dict[tuple[str, ...], int] | None = None,
        stream_lines: dict[tuple[str, ...], list[str]] | None = None,
        stream_returncodes: dict[tuple[str, ...], int] | None = None,
    ) -> None:
        self.responses = dict(responses or {})
        self.returncodes = dict(returncodes or {})
        self.stream_lines = dict(stream_lines or {})
        self.stream_returncodes = dict(stream_returncodes or {})
        self.calls: list[tuple[str, ...]] = []

    def run(
        self, command, *, cwd: Path | None = None, timeout: float | None = None
    ) -> CommandResult:
        args = tuple(str(part) for part in command)
        self.calls.append(args)
        assert args in self.responses, f"未预置命令：{args}"
        return CommandResult(args, self.returncodes.get(args, 0), self.responses[args], "")

    def stream(self, command, *, on_line, cwd: Path | None = None) -> int:
        args = tuple(str(part) for part in command)
        self.calls.append(args)
        for line in self.stream_lines.get(args, []):
            on_line(line)
        return self.stream_returncodes.get(args, 0)


@pytest.fixture
def fake_runner() -> Callable[..., FakeRunner]:
    return FakeRunner
