"""所有外部命令的唯一执行入口：超时、编码、日志集中在此处理。"""

from __future__ import annotations

import locale
import logging
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 60.0
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class SubprocessTimeoutError(RuntimeError):
    """子进程在限定时间内未结束。"""

    def __init__(self, command: Sequence[str], timeout: float) -> None:
        super().__init__(f"命令超时（{timeout:g}s）：{' '.join(command)}")
        self.command = tuple(command)
        self.timeout = timeout


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _decode_output(raw: bytes) -> str:
    """子进程输出可能是 UTF-8（conda/pip --json）或系统 ANSI 代码页，按序尝试。"""
    for encoding in ("utf-8", locale.getpreferredencoding(False)):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


class SubprocessRunner:
    """封装 subprocess 调用，屏蔽 Windows 控制台窗口与编码差异。"""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._timeout = timeout

    def run(self, command: Sequence[str | Path], *, cwd: Path | None = None) -> CommandResult:
        args = tuple(str(part) for part in command)
        logger.debug("执行命令：%s", args)
        try:
            completed = subprocess.run(
                args,
                cwd=cwd,
                capture_output=True,
                timeout=self._timeout,
                creationflags=_NO_WINDOW,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SubprocessTimeoutError(args, self._timeout) from exc
        result = CommandResult(
            args,
            completed.returncode,
            _decode_output(completed.stdout),
            _decode_output(completed.stderr),
        )
        logger.debug(
            "命令结束 rc=%s stdout=%r stderr=%r",
            result.returncode,
            result.stdout,
            result.stderr,
        )
        return result
