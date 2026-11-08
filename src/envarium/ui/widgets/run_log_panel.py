"""底部运行日志面板：把后台命令与输出实时呈现为可折叠终端。"""

from __future__ import annotations

import html

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from envarium.infrastructure.run_log import RunLog, RunLogEntry, RunLogKind
from envarium.ui.theme.tokens import TERMINAL


class RunLogPanel(QFrame):
    """全局运行日志：订阅 RunLog，并切回界面线程渲染。"""

    _entry_received = Signal(object)

    def __init__(self, run_log: RunLog, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RunLogPanel")
        self._run_log = run_log

        title = QLabel("运行日志")
        title.setObjectName("SectionTitle")

        self._clear_button = QPushButton("清空")
        self._clear_button.clicked.connect(self._clear)
        self._toggle_button = QPushButton("收起")
        self._toggle_button.setCheckable(True)
        self._toggle_button.toggled.connect(self._on_collapsed)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self._clear_button)
        header.addWidget(self._toggle_button)

        self._body = QPlainTextEdit()
        self._body.setObjectName("RunLog")
        self._body.setReadOnly(True)
        self._body.setMaximumBlockCount(2000)
        self._body.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("Consolas")
        font.setPointSize(9)
        self._body.setFont(font)
        # 40 = 文档上下边距 + 边框与内边距 + 常显的水平滚动条 + 行高取整余量
        self._body.setFixedHeight(self._body.fontMetrics().lineSpacing() * 6 + 40)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 10)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self._body)

        self._entry_received.connect(self._append_entry)
        self._run_log.subscribe(self._on_entry)
        for entry in self._run_log.entries():
            self._append_entry(entry)

    def _on_entry(self, entry: RunLogEntry) -> None:
        # 可能来自工作线程，emit 后由 Qt 排队回界面线程
        self._entry_received.emit(entry)

    def _append_entry(self, entry: RunLogEntry) -> None:
        color = {
            RunLogKind.COMMAND: TERMINAL.command,
            RunLogKind.OUTPUT: TERMINAL.foreground,
            RunLogKind.INFO: TERMINAL.info,
            RunLogKind.ERROR: TERMINAL.error,
        }[entry.kind]
        prompt = "&gt; " if entry.kind is RunLogKind.COMMAND else ""
        stamp = entry.created_at.strftime("%H:%M:%S")
        self._body.appendHtml(
            f'<span style="color:{TERMINAL.timestamp}">{stamp}</span> '
            f'<span style="color:{color}">{prompt}{html.escape(entry.text)}</span>'
        )

    def _clear(self) -> None:
        self._run_log.clear()
        self._body.clear()

    def _on_collapsed(self, collapsed: bool) -> None:
        self._body.setVisible(not collapsed)
        self._toggle_button.setText("展开" if collapsed else "收起")
