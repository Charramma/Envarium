"""右侧环境详情面板：元信息、异步统计结果与环境操作入口。"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from envarium.core.models import Environment, EnvironmentMetrics, Package
from envarium.ui.formatting import breakable_path, format_size, format_time
from envarium.ui.labels import KIND_LABELS

_PATH_KEYS = frozenset({"环境路径", "解释器"})


class DetailPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DetailPanel")
        self.setFixedWidth(300)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(18, 16, 18, 16)
        self._outer.setSpacing(0)
        self._body: QWidget | None = None
        self._actions: list[QAction] = []
        self._buttons: list[QPushButton] = []
        self._environment: Environment | None = None
        self._metrics: EnvironmentMetrics | None = None
        self._packages: Sequence[Package] | None = None
        self._packages_error = ""
        self._render()

    def set_actions(self, actions: Sequence[QAction]) -> None:
        self._actions = list(actions)
        self._render()

    def sync_actions(self) -> None:
        for button, action in zip(self._buttons, self._actions, strict=False):
            button.setEnabled(action.isEnabled())

    def show_environment(
        self,
        environment: Environment | None,
        *,
        metrics: EnvironmentMetrics | None = None,
        packages: Sequence[Package] | None = None,
        packages_error: str = "",
    ) -> None:
        self._environment = environment
        self._metrics = metrics
        self._packages = packages
        self._packages_error = packages_error
        self._render()

    def _render(self) -> None:
        if self._body is not None:
            self._outer.removeWidget(self._body)
            self._body.deleteLater()
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._body = body
        self._buttons = []
        self._outer.addWidget(body, 0, Qt.AlignmentFlag.AlignTop)

        if self._environment is None:
            hint = QLabel("未选择环境\n\n在左侧列表中选择一个环境查看详情。")
            hint.setObjectName("EmptyHint")
            hint.setWordWrap(True)
            layout.addWidget(hint)
            return

        title = QLabel("环境详情")
        title.setObjectName("DetailTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        for row, (key, value) in enumerate(self._rows()):
            key_label = QLabel(key)
            key_label.setObjectName("DetailKey")
            is_path = key in _PATH_KEYS
            value_label = QLabel(breakable_path(value) if is_path else value)
            value_label.setObjectName("DetailValue")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            if is_path:
                value_label.setToolTip(value)
            grid.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value_label, row, 1)
        layout.addLayout(grid)

        if not self._actions:
            return
        layout.addSpacing(4)
        actions = QGridLayout()
        actions.setSpacing(6)
        for index, action in enumerate(self._actions):
            button = QPushButton(action.text())
            if action.property("danger"):
                button.setObjectName("Danger")
            button.setEnabled(action.isEnabled())
            button.clicked.connect(action.trigger)
            actions.addWidget(button, index // 2, index % 2)
            self._buttons.append(button)
        layout.addLayout(actions)

    def _rows(self) -> list[tuple[str, str]]:
        environment = self._environment
        assert environment is not None
        metrics = self._metrics
        return [
            ("名称", environment.name),
            ("类型", KIND_LABELS[environment.kind]),
            ("Python 版本", environment.version or "未知"),
            ("环境路径", str(environment.path)),
            ("解释器", str(environment.interpreter)),
            ("大小", format_size(metrics.size_bytes) if metrics else "统计中…"),
            ("最后修改", format_time(metrics.modified_at) if metrics else "—"),
            ("可写", "—" if metrics is None else ("是" if metrics.writable else "否")),
            ("状态", self._status_text()),
            ("包数量", self._package_count_text()),
            ("pip 版本", self._pip_version_text()),
        ]

    def _status_text(self) -> str:
        environment = self._environment
        assert environment is not None
        if not environment.available:
            return "已失效（路径不存在）"
        return "当前 PATH 生效" if environment.on_path else "正常"

    def _package_count_text(self) -> str:
        if self._packages_error:
            return "读取失败"
        if self._packages is None:
            return "加载中…"
        return f"{len(self._packages)} 个"

    def _pip_version_text(self) -> str:
        if self._packages_error:
            return "—"
        if self._packages is None:
            return "加载中…"
        version = next(
            (package.version for package in self._packages if package.name.lower() == "pip"),
            "",
        )
        return version or "未安装"
