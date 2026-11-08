"""把阻塞调用移出 GUI 线程的唯一入口。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal

logger = logging.getLogger(__name__)

T = TypeVar("T")


class _JobSignals(QObject):
    done = Signal(object)
    failed = Signal(object)
    finished = Signal()


class _Job(QRunnable):
    def __init__(self, work: Callable[[], Any]) -> None:
        super().__init__()
        self.signals = _JobSignals()
        self._work = work
        self.setAutoDelete(False)

    def run(self) -> None:
        try:
            result = self._work()
        except Exception as error:
            logger.exception("后台任务失败")
            self.signals.failed.emit(error)
        else:
            self.signals.done.emit(result)
        finally:
            self.signals.finished.emit()


class BackgroundRunner(QObject):
    """在独立线程池中执行工作函数，回调固定回到 GUI 线程。"""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._jobs: set[_Job] = set()

    def submit(
        self,
        work: Callable[[], T],
        *,
        on_done: Callable[[T], None],
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        job = _Job(work)
        job.signals.done.connect(on_done, Qt.ConnectionType.QueuedConnection)
        if on_error is not None:
            job.signals.failed.connect(on_error, Qt.ConnectionType.QueuedConnection)
        job.signals.finished.connect(
            lambda: self._jobs.discard(job), Qt.ConnectionType.QueuedConnection
        )
        self._jobs.add(job)
        self._pool.start(job)
