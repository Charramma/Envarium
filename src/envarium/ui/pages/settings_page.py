"""设置页：主题、默认终端、镜像源与日志。"""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from envarium.core.mirrors import MIRRORS, Mirror
from envarium.core.models import TerminalKind
from envarium.infrastructure.config_store import AppConfig, ConfigStore, Theme
from envarium.infrastructure.logging_setup import log_directory
from envarium.services.environment_service import EnvironmentService
from envarium.ui.labels import TERMINAL_LABELS
from envarium.ui.tasks import BackgroundRunner
from envarium.ui.widgets.combo import ComboBox


class SettingsPage(QWidget):
    theme_changed = Signal(object)

    def __init__(
        self,
        config: AppConfig,
        config_store: ConfigStore,
        environment_service: EnvironmentService,
        runner: BackgroundRunner,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._config_store = config_store
        self._environment_service = environment_service
        self._runner = runner
        self._mirrors = {mirror.key: mirror for mirror in MIRRORS}

        title = QLabel("设置")
        title.setObjectName("PageTitle")

        theme_label = QLabel("主题")
        theme_label.setObjectName("DetailValue")
        self._theme_combo = ComboBox()
        self._theme_combo.addItem("浅色", Theme.LIGHT)
        self._theme_combo.addItem("深色", Theme.DARK)
        self._theme_combo.setCurrentIndex(self._theme_combo.findData(config.theme))
        self._theme_combo.setFixedWidth(160)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)

        terminal_label = QLabel("默认终端")
        terminal_label.setObjectName("DetailValue")
        self._terminal_combo = ComboBox()
        for kind in TerminalKind:
            self._terminal_combo.addItem(TERMINAL_LABELS[kind], kind)
        self._terminal_combo.setCurrentIndex(
            max(0, self._terminal_combo.findData(config.terminal))
        )
        self._terminal_combo.setFixedWidth(200)
        self._terminal_combo.currentIndexChanged.connect(self._on_terminal_changed)

        mirror_label = QLabel("镜像源")
        mirror_label.setObjectName("DetailValue")
        mirror_hint = QLabel("写入用户级 pip.ini 与 conda channels，影响全局终端与包管理操作。")
        mirror_hint.setObjectName("Hint")
        self._mirror_combo = ComboBox()
        for mirror in MIRRORS:
            self._mirror_combo.addItem(mirror.label, mirror.key)
        self._mirror_combo.setFixedWidth(200)
        self._mirror_button = QPushButton("应用镜像源")
        self._mirror_button.clicked.connect(self._apply_mirror)
        self._mirror_status = QLabel()
        self._mirror_status.setObjectName("Hint")
        mirror_row = QHBoxLayout()
        mirror_row.setSpacing(8)
        mirror_row.addWidget(self._mirror_combo)
        mirror_row.addWidget(self._mirror_button)
        mirror_row.addWidget(self._mirror_status, 1)

        log_label = QLabel("日志")
        log_label.setObjectName("DetailValue")
        log_path = QLabel(str(log_directory()))
        log_path.setObjectName("Hint")
        log_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        open_logs_button = QPushButton("打开日志目录")
        open_logs_button.clicked.connect(self._open_log_dir)
        export_logs_button = QPushButton("导出诊断日志…")
        export_logs_button.clicked.connect(self._export_logs)
        log_buttons = QHBoxLayout()
        log_buttons.setSpacing(8)
        log_buttons.addWidget(open_logs_button)
        log_buttons.addWidget(export_logs_button)
        log_buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(theme_label)
        layout.addWidget(self._theme_combo, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(12)
        layout.addWidget(terminal_label)
        layout.addWidget(self._terminal_combo, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(16)
        layout.addWidget(mirror_label)
        layout.addWidget(mirror_hint)
        layout.addLayout(mirror_row)
        layout.addSpacing(16)
        layout.addWidget(log_label)
        layout.addWidget(log_path)
        layout.addLayout(log_buttons)
        layout.addStretch(1)

    def _on_theme_changed(self, index: int) -> None:
        # Qt 会把枚举还原为 str，这里收敛回 Theme
        theme = Theme(self._theme_combo.itemData(index))
        if theme == self._config.theme:
            return
        self._config.theme = theme
        self._config_store.save(self._config)
        self.theme_changed.emit(theme)

    def _on_terminal_changed(self, index: int) -> None:
        terminal = TerminalKind(self._terminal_combo.itemData(index))
        if terminal == self._config.terminal:
            return
        self._config.terminal = terminal
        self._config_store.save(self._config)

    def _apply_mirror(self) -> None:
        mirror = self._mirrors[self._mirror_combo.currentData()]
        self._mirror_button.setEnabled(False)
        self._mirror_status.setText("正在写入镜像配置…")
        self._runner.submit(
            lambda: self._environment_service.configure_mirror(mirror),
            on_done=lambda _result: self._mirror_done(mirror),
            on_error=self._mirror_failed,
        )

    def _mirror_done(self, mirror: Mirror) -> None:
        self._mirror_button.setEnabled(True)
        self._mirror_status.setText(f"已应用：{mirror.label}")

    def _mirror_failed(self, error: Exception) -> None:
        self._mirror_button.setEnabled(True)
        self._mirror_status.setText("镜像配置失败")
        QMessageBox.critical(self, "镜像配置失败", str(error))

    def _open_log_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_directory())))

    def _export_logs(self) -> None:
        source = log_directory() / "envarium.log"
        if not source.exists():
            QMessageBox.information(self, "暂无日志", "当前还没有生成日志文件。")
            return
        target, _selected = QFileDialog.getSaveFileName(
            self,
            "导出诊断日志",
            str(Path.home() / "envarium-diagnostics.log"),
            "日志文件 (*.log)",
        )
        if not target:
            return
        shutil.copy2(source, target)
        QMessageBox.information(self, "已导出", f"诊断日志已保存到：\n{target}")
