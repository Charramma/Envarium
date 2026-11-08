"""运行日志：外部命令与输出的实时记录，供界面底部终端展示。"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class RunLogKind(StrEnum):
    """运行日志条目类型。"""

    COMMAND = "command"
    OUTPUT = "output"
    INFO = "info"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class RunLogEntry:
    """一条带时间的运行日志。"""

    created_at: datetime
    kind: RunLogKind
    text: str


Subscriber = Callable[[RunLogEntry], None]


def format_command(command: Sequence[str]) -> str:
    """按 Shell 习惯给含空格的参数加引号。"""
    return " ".join(f'"{part}"' if " " in part else part for part in command)


class RunLog:
    """线程安全的内存日志：写入来自任意工作线程，订阅方负责切回界面线程。"""

    def __init__(self, max_entries: int = 2000) -> None:
        self._entries: deque[RunLogEntry] = deque(maxlen=max_entries)
        self._subscribers: list[Subscriber] = []
        self._lock = threading.Lock()

    def entries(self) -> list[RunLogEntry]:
        with self._lock:
            return list(self._entries)

    def subscribe(self, subscriber: Subscriber) -> None:
        with self._lock:
            self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber: Subscriber) -> None:
        with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def record_command(self, command: Sequence[str]) -> None:
        self._append(format_command(command), RunLogKind.COMMAND)

    def record_output(self, text: str) -> None:
        self._append(text, RunLogKind.OUTPUT)

    def record_info(self, text: str) -> None:
        self._append(text, RunLogKind.INFO)

    def record_error(self, text: str) -> None:
        self._append(text, RunLogKind.ERROR)

    def _append(self, text: str, kind: RunLogKind) -> None:
        entry = RunLogEntry(datetime.now(), kind, text)
        with self._lock:
            self._entries.append(entry)
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            subscriber(entry)
