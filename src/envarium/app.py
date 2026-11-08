"""应用引导：装配基础设施、服务与界面。"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from envarium.infrastructure.config_store import ConfigStore
from envarium.infrastructure.logging_setup import configure_logging
from envarium.infrastructure.run_log import RunLog
from envarium.infrastructure.subprocess_runner import SubprocessRunner
from envarium.platforms.windows.operations import WindowsOperations
from envarium.platforms.windows.provider import WindowsProvider
from envarium.platforms.windows.runtime import WindowsRuntimeProbe
from envarium.services.environment_service import EnvironmentService
from envarium.services.overview_service import OverviewService
from envarium.services.package_service import PackageService
from envarium.ui.main_window import MainWindow
from envarium.ui.theme.style import apply_theme

_ASSETS = Path(__file__).parent / "assets"
_APP_USER_MODEL_ID = "Charramma.Envarium"


def main() -> int:
    configure_logging()
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_USER_MODEL_ID)
    app = QApplication(sys.argv)
    app.setApplicationName("Envarium")
    app.setApplicationDisplayName("Envarium")
    app.setOrganizationName("Charramma")
    app.setWindowIcon(QIcon(str(_ASSETS / "app.ico")))
    app.setStyle("Fusion")

    config_store = ConfigStore()
    config = config_store.load()
    apply_theme(app, config.theme)

    run_log = RunLog()
    runner = SubprocessRunner(run_log=run_log)
    operations = WindowsOperations(runner)
    environment_service = EnvironmentService(
        WindowsProvider(runner), operations, config_store
    )
    overview_service = OverviewService(WindowsRuntimeProbe(runner))
    package_service = PackageService(operations)
    window = MainWindow(
        environment_service,
        overview_service,
        package_service,
        config_store,
        config,
        run_log,
    )
    window.show()
    return app.exec()
