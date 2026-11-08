"""概览页：系统与工具链信息、受管理的环境清单。"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from envarium.core.models import Environment, OverviewData, PythonToolchain
from envarium.services.overview_service import OverviewService
from envarium.ui.tasks import BackgroundRunner

logger = logging.getLogger(__name__)


def _clear_layout(layout: QLayout) -> None:
    """移除布局内的全部子项，用于重复渲染动态区块。"""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
            continue
        child = item.layout()
        if child is not None:
            _clear_layout(child)


class OverviewPage(QWidget):
    """展示运行时信息，并作为默认首页。"""

    refresh_requested = Signal()

    def __init__(
        self,
        service: OverviewService,
        runner: BackgroundRunner,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._runner = runner
        self._environments: list[Environment] = []
        self._probed_keys: tuple[tuple[str, str], ...] | None = None
        self._probe_token = 0

        title = QLabel("概览")
        title.setObjectName("PageTitle")
        self._status = QLabel()
        self._status.setObjectName("StatusLabel")
        self._refresh_button = QPushButton("刷新")
        self._refresh_button.setObjectName("Primary")
        self._refresh_button.clicked.connect(self.refresh)

        header = QHBoxLayout()
        header.setSpacing(10)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self._status)
        header.addWidget(self._refresh_button)

        container = QWidget()
        sections = QVBoxLayout(container)
        sections.setContentsMargins(0, 0, 8, 0)
        sections.setSpacing(14)
        self._system_body = self._add_section(sections, "操作系统")
        self._python_body = self._add_section(sections, "Python 与 pip")
        self._conda_body = self._add_section(sections, "conda")
        self._venv_body = self._add_section(sections, "venv 环境")
        self._conda_env_body = self._add_section(sections, "conda 环境")
        sections.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addLayout(header)
        layout.addWidget(scroll, 1)

    def set_environments(self, environments: Sequence[Environment]) -> None:
        """接收环境库的刷新结果；环境未变化时不重复探测。"""
        environments = list(environments)
        self._environments = environments
        keys = tuple((item.key, item.version) for item in environments)
        if keys == self._probed_keys:
            return
        self._probe()

    def refresh(self) -> None:
        self._probe()
        self.refresh_requested.emit()

    def _add_section(self, parent: QVBoxLayout, title: str) -> QVBoxLayout:
        card = QFrame()
        card.setObjectName("DetailPanel")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        layout.addWidget(heading)
        body = QVBoxLayout()
        body.setSpacing(6)
        layout.addLayout(body)
        parent.addWidget(card)
        return body

    def _probe(self) -> None:
        self._probe_token += 1
        token = self._probe_token
        environments = list(self._environments)
        self._status.setText("正在读取运行时信息…")
        self._status.setToolTip("")
        self._runner.submit(
            lambda: self._service.snapshot(environments),
            on_done=lambda data: self._show_data(token, data),
            on_error=lambda error: self._show_error(token, error),
        )

    def _show_data(self, token: int, data: OverviewData) -> None:
        if token != self._probe_token:
            return
        self._probed_keys = tuple(
            (item.key, item.version) for item in self._environments
        )
        self._render_system(data)
        self._render_pythons(data)
        self._render_conda(data)
        self._render_venvs(data.venvs)
        self._render_conda_environments(data.conda_environments)
        self._status.setText("")

    def _show_error(self, token: int, error: Exception) -> None:
        if token != self._probe_token:
            return
        logger.warning("读取运行时信息失败：%s", error)
        self._status.setText("运行时信息读取失败")
        self._status.setToolTip(str(error))

    def _render_system(self, data: OverviewData) -> None:
        _clear_layout(self._system_body)
        self._system_body.addWidget(self._text(data.system.display))
        self._system_body.addWidget(
            self._hint(f"内核版本 {data.system.version} · {data.system.machine}")
        )

    def _render_pythons(self, data: OverviewData) -> None:
        _clear_layout(self._python_body)
        if not data.pythons:
            self._python_body.addWidget(self._hint("未发现从 python.org 安装的 Python。"))
            return
        for index, toolchain in enumerate(data.pythons):
            if index:
                self._python_body.addWidget(self._separator())
            self._python_body.addWidget(
                self._text(f"Python {toolchain.environment.version}", "SectionTitle")
            )
            self._python_body.addWidget(
                self._hint(str(toolchain.environment.interpreter))
            )
            self._python_body.addLayout(self._pip_row(toolchain))

    def _pip_row(self, toolchain: PythonToolchain) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self._text(f"pip {toolchain.pip_version or '未检测到 pip'}"))
        if toolchain.pip_path is not None:
            row.addWidget(self._hint(str(toolchain.pip_path)), 1)
        else:
            row.addStretch(1)
        button = QPushButton("升级 pip")
        button.setEnabled(toolchain.pip_path is not None)
        button.clicked.connect(
            lambda _checked=False, item=toolchain, target=button: self._upgrade_pip(
                item, target
            )
        )
        row.addWidget(button)
        return row

    def _render_conda(self, data: OverviewData) -> None:
        _clear_layout(self._conda_body)
        if data.conda is None:
            self._conda_body.addWidget(
                self._hint("未检测到 conda（Anaconda / Miniconda）。")
            )
            return
        self._conda_body.addWidget(
            self._text(f"conda {data.conda.version or '版本未知'}")
        )
        self._conda_body.addWidget(self._hint(str(data.conda.executable)))

    def _render_venvs(self, environments: Sequence[Environment]) -> None:
        self._render_environment_list(
            self._venv_body, environments, "尚未纳入任何 venv 环境。"
        )

    def _render_conda_environments(self, environments: Sequence[Environment]) -> None:
        self._render_environment_list(
            self._conda_env_body, environments, "未检测到 conda 环境。"
        )

    def _render_environment_list(
        self,
        body: QVBoxLayout,
        environments: Sequence[Environment],
        empty_hint: str,
    ) -> None:
        """渲染「名称 + Python 版本 + 路径」的环境清单。"""
        _clear_layout(body)
        if not environments:
            body.addWidget(self._hint(empty_hint))
            return
        for index, environment in enumerate(environments):
            if index:
                body.addWidget(self._separator())
            row = QHBoxLayout()
            row.setSpacing(10)
            row.addWidget(self._text(environment.name, "SectionTitle"))
            row.addWidget(self._hint(f"Python {environment.version or '未知'}"))
            row.addStretch(1)
            body.addLayout(row)
            body.addWidget(self._hint(str(environment.path)))

    def _upgrade_pip(self, toolchain: PythonToolchain, button: QPushButton) -> None:
        button.setEnabled(False)
        self._status.setText(
            f"正在升级 Python {toolchain.environment.version} 的 pip…"
        )
        self._runner.submit_stream(
            lambda log: self._service.upgrade_pip(toolchain, log),
            on_line=lambda _line: None,
            on_done=lambda _result: self._pip_upgraded(),
            on_error=lambda error: self._pip_failed(button, error),
        )

    def _pip_upgraded(self) -> None:
        self._status.setText("pip 已升级")
        self._probe()

    def _pip_failed(self, button: QPushButton, error: Exception) -> None:
        button.setEnabled(True)
        self._status.setText("pip 升级失败")
        QMessageBox.critical(self, "升级 pip 失败", str(error))

    @staticmethod
    def _text(value: str, object_name: str = "DetailValue") -> QLabel:
        label = QLabel(value)
        label.setObjectName(object_name)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setWordWrap(True)
        return label

    @staticmethod
    def _hint(value: str) -> QLabel:
        label = OverviewPage._text(value, "Hint")
        return label

    @staticmethod
    def _separator() -> QFrame:
        line = QFrame()
        line.setObjectName("Separator")
        line.setFixedHeight(1)
        return line
