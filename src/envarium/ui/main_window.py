"""主窗口：顶部菜单栏 + 侧边导航 + 内容区。"""

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
from envarium.core.models import Environment
from envarium.infrastructure.config_store import AppConfig, ConfigStore, Theme
from envarium.infrastructure.run_log import RunLog
from envarium.services.environment_service import EnvironmentService
from envarium.services.overview_service import OverviewService
from envarium.services.package_service import PackageService
from envarium.ui.pages.about_page import AboutPage
from envarium.ui.pages.environments_page import EnvironmentsPage
from envarium.ui.pages.overview_page import OverviewPage
from envarium.ui.pages.packages_page import PackagesPage
from envarium.ui.pages.settings_page import SettingsPage
from envarium.ui.tasks import BackgroundRunner
from envarium.ui.theme.style import apply_theme
from envarium.ui.theme.tokens import palette_for
from envarium.ui.widgets.run_log_panel import RunLogPanel
from envarium.ui.widgets.sidebar import Sidebar


class MainWindow(QMainWindow):
    def __init__(
        self,
        environment_service: EnvironmentService,
        overview_service: OverviewService,
        package_service: PackageService,
        config_store: ConfigStore,
        config: AppConfig,
        run_log: RunLog,
    ) -> None:
        super().__init__()
        self._config_store = config_store
        self._config = config
        self.setWindowTitle("Envarium")
        self.resize(1320, 860)

        self._runner = BackgroundRunner(self)
        self._palette = palette_for(config.theme)
        self._sidebar = Sidebar(("概览", "环境", "包管理"), __version__)
        self._stack = QStackedWidget()
        self._overview_page = OverviewPage(overview_service, self._runner)
        self._environments_page = EnvironmentsPage(
            environment_service,
            package_service,
            self._runner,
            config,
            self._palette,
        )
        self._packages_page = PackagesPage(package_service, self._runner)
        self._settings_page = SettingsPage(
            config, config_store, environment_service, self._runner
        )
        self._about_page = AboutPage()
        for page in (
            self._overview_page,
            self._environments_page,
            self._packages_page,
            self._settings_page,
            self._about_page,
        ):
            self._stack.addWidget(page)

        self._run_log_panel = RunLogPanel(run_log)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 14, 16, 14)
        content_layout.setSpacing(12)
        content_layout.addWidget(self._stack, 1)
        content_layout.addWidget(self._run_log_panel)

        root = QWidget()
        root.setObjectName("Root")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._sidebar)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)

        menu_bar = self.menuBar()
        settings_action = menu_bar.addAction("设置")
        about_action = menu_bar.addAction("关于")
        settings_action.triggered.connect(lambda: self._show_page(self._settings_page))
        about_action.triggered.connect(lambda: self._show_page(self._about_page))

        self._packages_page.set_environments(self._environments_page.environments())
        self._overview_page.set_environments(self._environments_page.environments())
        self._sidebar.page_selected.connect(self._stack.setCurrentIndex)
        self._environments_page.environments_changed.connect(
            self._packages_page.set_environments
        )
        self._environments_page.environments_changed.connect(
            self._overview_page.set_environments
        )
        self._environments_page.manage_packages_requested.connect(self._open_packages)
        self._overview_page.refresh_requested.connect(self._environments_page.refresh)
        self._settings_page.theme_changed.connect(self._on_theme_changed)

    def _open_packages(self, environment: Environment) -> None:
        self._packages_page.show_environment(environment)
        self._sidebar.select(2)

    def _show_page(self, page: QWidget) -> None:
        self._stack.setCurrentWidget(page)
        self._sidebar.clear_selection()

    def _on_theme_changed(self, theme: Theme) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app, theme)
        self._palette = palette_for(theme)
        self._environments_page.apply_palette(self._palette)
