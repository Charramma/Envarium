"""右侧环境详情面板。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from envarium.core.models import Environment
from envarium.ui.labels import KIND_LABELS


def _details(environment: Environment) -> list[tuple[str, str]]:
    details = [
        ("名称", environment.name),
        ("类型", KIND_LABELS[environment.kind]),
        ("Python 版本", environment.version or "未知"),
        ("环境路径", str(environment.path)),
        ("解释器", str(environment.interpreter)),
    ]
    if environment.is_base:
        details.append(("标记", "base 基础环境"))
    return details


class DetailPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DetailPanel")
        self.setFixedWidth(320)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(18, 16, 18, 16)
        self._layout.setSpacing(8)
        self.show_environment(None)

    def show_environment(self, environment: Environment | None) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if environment is None:
            hint = QLabel("未选择环境\n\n在左侧列表中选择一个环境查看详情。")
            hint.setObjectName("EmptyHint")
            hint.setWordWrap(True)
            self._layout.addWidget(hint)
            self._layout.addStretch(1)
            return

        title = QLabel("环境详情")
        title.setObjectName("DetailTitle")
        self._layout.addWidget(title)
        self._layout.addSpacing(6)

        for key, value in _details(environment):
            key_label = QLabel(key)
            key_label.setObjectName("DetailKey")
            value_label = QLabel(value)
            value_label.setObjectName("DetailValue")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._layout.addWidget(key_label)
            self._layout.addWidget(value_label)
        self._layout.addStretch(1)
