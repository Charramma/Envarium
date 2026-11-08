"""设置页：主题、venv 扫描目录、日志目录。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from envarium.infrastructure.config_store import AppConfig, ConfigStore, Theme
from envarium.infrastructure.logging_setup import log_directory


class SettingsPage(QWidget):
    theme_changed = Signal(object)
    scan_roots_changed = Signal()

    def __init__(
        self, config: AppConfig, config_store: ConfigStore, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._config_store = config_store

        title = QLabel("设置")
        title.setObjectName("PageTitle")

        theme_label = QLabel("主题")
        theme_label.setObjectName("DetailValue")
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("浅色", Theme.LIGHT)
        self._theme_combo.addItem("深色", Theme.DARK)
        self._theme_combo.setCurrentIndex(self._theme_combo.findData(config.theme))
        self._theme_combo.setFixedWidth(160)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)

        roots_label = QLabel("venv 扫描目录")
        roots_label.setObjectName("DetailValue")
        roots_hint = QLabel("在下列目录中（最多 3 层）查找 venv 环境。")
        roots_hint.setObjectName("Hint")

        self._roots_list = QListWidget()
        self._roots_list.setFixedHeight(150)
        self._roots_list.setMaximumWidth(640)
        for root in config.venv_scan_roots:
            self._roots_list.addItem(str(root))

        add_button = QPushButton("添加目录")
        add_button.clicked.connect(self._add_scan_root)
        remove_button = QPushButton("移除")
        remove_button.clicked.connect(self._remove_scan_root)
        roots_buttons = QHBoxLayout()
        roots_buttons.setSpacing(8)
        roots_buttons.addWidget(add_button)
        roots_buttons.addWidget(remove_button)
        roots_buttons.addStretch(1)

        log_label = QLabel("日志")
        log_label.setObjectName("DetailValue")
        log_path = QLabel(str(log_directory()))
        log_path.setObjectName("Hint")
        log_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        open_logs_button = QPushButton("打开日志目录")
        open_logs_button.clicked.connect(self._open_log_dir)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(theme_label)
        layout.addWidget(self._theme_combo, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(16)
        layout.addWidget(roots_label)
        layout.addWidget(roots_hint)
        layout.addWidget(self._roots_list)
        layout.addLayout(roots_buttons)
        layout.addSpacing(16)
        layout.addWidget(log_label)
        layout.addWidget(log_path)
        layout.addWidget(open_logs_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

    def _on_theme_changed(self, index: int) -> None:
        # Qt 会把枚举还原为 str，这里收敛回 Theme
        theme = Theme(self._theme_combo.itemData(index))
        if theme == self._config.theme:
            return
        self._config.theme = theme
        self._config_store.save(self._config)
        self.theme_changed.emit(theme)

    def _add_scan_root(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择 venv 扫描目录")
        if not directory:
            return
        path = Path(directory)
        if path in self._config.venv_scan_roots:
            return
        self._config.venv_scan_roots.append(path)
        self._roots_list.addItem(str(path))
        self._save_scan_roots()

    def _remove_scan_root(self) -> None:
        row = self._roots_list.currentRow()
        if row < 0:
            return
        self._roots_list.takeItem(row)
        del self._config.venv_scan_roots[row]
        self._save_scan_roots()

    def _save_scan_roots(self) -> None:
        self._config_store.save(self._config)
        self.scan_roots_changed.emit()

    def _open_log_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_directory())))
