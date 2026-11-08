"""关于页。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from envarium import __version__

_ABOUT_TEXT = f"""Envarium {__version__}

统一发现与管理 Windows 上的 Python 环境。

许可证：MIT
项目地址：https://github.com/Charramma/Envarium

第三方组件
PySide6 / Qt for Python — LGPL-3.0
platformdirs — MIT
pydantic — MIT
"""


class AboutPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        title = QLabel("关于")
        title.setObjectName("PageTitle")

        body = QLabel(_ABOUT_TEXT)
        body.setObjectName("DetailValue")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(body)
        layout.addStretch(1)
