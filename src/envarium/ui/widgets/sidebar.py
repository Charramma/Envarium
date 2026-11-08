"""左侧导航栏。"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QLabel, QPushButton, QVBoxLayout, QWidget


class Sidebar(QWidget):
    page_selected = Signal(int)

    def __init__(self, items: Sequence[str], version: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(196)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 18, 12, 14)
        layout.setSpacing(6)

        title = QLabel("Envarium")
        title.setObjectName("AppTitle")
        subtitle = QLabel("Python 环境管理")
        subtitle.setObjectName("AppSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(14)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for index, text in enumerate(items):
            button = QPushButton(text)
            button.setProperty("nav", True)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(button, index)
            layout.addWidget(button)
            if index == 0:
                button.setChecked(True)
        self._group.idClicked.connect(self.page_selected)

        layout.addStretch(1)
        version_label = QLabel(f"v{version}")
        version_label.setObjectName("VersionLabel")
        layout.addWidget(version_label)

    def select(self, index: int) -> None:
        button = self._group.button(index)
        if button is not None:
            button.setChecked(True)
            self.page_selected.emit(index)

    def clear_selection(self) -> None:
        self._group.setExclusive(False)
        for button in self._group.buttons():
            button.setChecked(False)
        self._group.setExclusive(True)
