"""应用引导：装配基础设施、服务与界面。"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from envarium.infrastructure.config_store import ConfigStore
from envarium.infrastructure.logging_setup import configure_logging
from envarium.infrastructure.subprocess_runner import SubprocessRunner
from envarium.platforms.windows.operations import WindowsOperations
from envarium.platforms.windows.provider import WindowsProvider
from envarium.services.environment_service import EnvironmentService
from envarium.services.package_service import PackageService
from envarium.ui.main_window import MainWindow
from envarium.ui.theme.style import apply_theme


def main() -> int:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Envarium")
    app.setApplicationDisplayName("Envarium")
    app.setOrganizationName("Charramma")
    app.setStyle("Fusion")

    config_store = ConfigStore()
    config = config_store.load()
    apply_theme(app, config.theme)

    runner = SubprocessRunner()
    operations = WindowsOperations(runner)
    environment_service = EnvironmentService(
        WindowsProvider(runner), operations, config_store
    )
    package_service = PackageService(operations)
    window = MainWindow(environment_service, package_service, config_store, config)
    window.show()
    return app.exec()
