"""主窗口：侧边导航 + 内容区。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from envarium import __version__
from envarium.infrastructure.config_store import AppConfig, ConfigStore, Theme
from envarium.services.environment_service import EnvironmentService
from envarium.ui.pages.about_page import AboutPage
from envarium.ui.pages.environments_page import EnvironmentsPage
from envarium.ui.pages.settings_page import SettingsPage
from envarium.ui.tasks import BackgroundRunner
from envarium.ui.theme.style import apply_theme
from envarium.ui.theme.tokens import palette_for
from envarium.ui.widgets.sidebar import Sidebar


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: EnvironmentService,
        config_store: ConfigStore,
        config: AppConfig,
    ) -> None:
        super().__init__()
        self._config_store = config_store
        self._config = config
        self.setWindowTitle("Envarium")
        self.resize(1180, 760)

        self._runner = BackgroundRunner(self)
        self._sidebar = Sidebar(("环境", "设置", "关于"), __version__)
        self._stack = QStackedWidget()
        self._environments_page = EnvironmentsPage(
            service, self._runner, palette_for(config.theme)
        )
        self._settings_page = SettingsPage(config, config_store)
        self._about_page = AboutPage()
        for page in (self._environments_page, self._settings_page, self._about_page):
            self._stack.addWidget(page)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 18, 20, 18)
        content_layout.addWidget(self._stack)

        root = QWidget()
        root.setObjectName("Root")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._sidebar)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)

        self._sidebar.page_selected.connect(self._stack.setCurrentIndex)
        self._settings_page.theme_changed.connect(self._on_theme_changed)
        self._settings_page.scan_roots_changed.connect(self._environments_page.refresh)

    def _on_theme_changed(self, theme: Theme) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app, theme)
        self._environments_page.apply_palette(palette_for(theme))
