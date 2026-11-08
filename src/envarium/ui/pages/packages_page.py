"""包管理页：查看环境已安装包，执行安装与卸载。"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from envarium.core.models import Environment, Package
from envarium.core.ports import LineSink
from envarium.services.package_service import PackageService
from envarium.ui.labels import KIND_LABELS
from envarium.ui.tasks import BackgroundRunner
from envarium.ui.widgets.combo import ComboBox

_HEADERS = ("名称", "版本")
_INVALID_INDEX = QModelIndex()


class PackageTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._packages: list[Package] = []

    def package_at(self, row: int) -> Package:
        return self._packages[row]

    def set_packages(self, packages: list[Package]) -> None:
        self.beginResetModel()
        self._packages = list(packages)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:
        return 0 if parent.isValid() else len(self._packages)

    def columnCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:
        return 0 if parent.isValid() else len(_HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = 0):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = 0):
        if not index.isValid():
            return None
        package = self._packages[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return package.name if index.column() == 0 else package.version
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{package.name} {package.version}"
        return None


class _PackageFilter(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._needle = ""

    def set_needle(self, needle: str) -> None:
        self._needle = needle.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._needle:
            return True
        package: Package = self.sourceModel().package_at(source_row)
        return self._needle in package.name.lower()


class PackagesPage(QWidget):
    def __init__(
        self,
        service: PackageService,
        runner: BackgroundRunner,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._runner = runner
        self._environments: list[Environment] = []
        self._by_key: dict[str, Environment] = {}
        self._packages: list[Package] = []
        self._busy = False

        title = QLabel("包管理")
        title.setObjectName("PageTitle")

        self._combo = ComboBox()
        self._combo.setMinimumWidth(340)

        self._refresh_button = QPushButton("刷新")
        self._status = QLabel()
        self._status.setObjectName("StatusLabel")

        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索包名")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedWidth(220)

        self._model = PackageTableModel(self)
        self._proxy = _PackageFilter(self)
        self._proxy.setSourceModel(self._model)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setWordWrap(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(32)
        self._table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 160)

        self._install_input = QLineEdit()
        self._install_input.setPlaceholderText(
            "输入包名，多个用空格分隔，例如 numpy pandas==2.2.0"
        )
        self._install_button = QPushButton("安装")
        self._install_button.setObjectName("Primary")
        self._uninstall_button = QPushButton("卸载")

        log_label = QLabel("操作日志")
        log_label.setObjectName("SectionTitle")
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(180)
        self._log.setPlaceholderText("安装或卸载时的命令输出会显示在这里。")

        environment_row = QHBoxLayout()
        environment_row.setSpacing(10)
        environment_row.addWidget(self._combo)
        environment_row.addWidget(self._refresh_button)
        environment_row.addStretch(1)
        environment_row.addWidget(self._status)

        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        search_row.addWidget(self._search)
        search_row.addStretch(1)

        install_row = QHBoxLayout()
        install_row.setSpacing(10)
        install_row.addWidget(self._install_input, 1)
        install_row.addWidget(self._install_button)
        install_row.addWidget(self._uninstall_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addLayout(environment_row)
        layout.addLayout(search_row)
        layout.addWidget(self._table, 1)
        layout.addLayout(install_row)
        layout.addWidget(log_label)
        layout.addWidget(self._log)

        self._combo.currentIndexChanged.connect(self._on_environment_changed)
        self._refresh_button.clicked.connect(self._reload)
        self._search.textChanged.connect(self._proxy.set_needle)
        self._table.selectionModel().currentRowChanged.connect(
            lambda _current, _previous: self._update_buttons()
        )
        self._install_button.clicked.connect(self._install)
        self._uninstall_button.clicked.connect(self._uninstall)
        self._install_input.returnPressed.connect(self._install)

        self._update_buttons()

    def set_environments(self, environments: list[Environment]) -> None:
        previous = self._current_key()
        self._environments = list(environments)
        self._by_key = {environment.key: environment for environment in environments}
        self._combo.blockSignals(True)
        self._combo.clear()
        for environment in environments:
            suffix = "" if environment.available else "（已失效）"
            version = environment.version or "—"
            self._combo.addItem(
                f"{environment.name} · {KIND_LABELS[environment.kind]} · {version}{suffix}",
                environment.key,
            )
        if self._combo.count():
            index = self._combo.findData(previous) if previous else -1
            self._combo.setCurrentIndex(index if index >= 0 else 0)
        self._combo.blockSignals(False)
        self._on_environment_changed()

    def show_environment(self, environment: Environment) -> None:
        index = self._combo.findData(environment.key)
        if index < 0:
            return
        if index == self._combo.currentIndex():
            self._on_environment_changed()
        else:
            self._combo.setCurrentIndex(index)

    def _current_key(self) -> str | None:
        return self._combo.currentData() if self._combo.count() else None

    def _current_environment(self) -> Environment | None:
        key = self._current_key()
        return self._by_key.get(key) if key else None

    def _is_current(self, environment: Environment) -> bool:
        return self._current_key() == environment.key

    def _on_environment_changed(self) -> None:
        environment = self._current_environment()
        self._packages = []
        self._model.set_packages([])
        self._search.clear()
        self._update_buttons()
        if environment is None:
            self._status.setText("未选择环境")
            return
        self._reload()

    def _reload(self) -> None:
        environment = self._current_environment()
        if environment is None or self._busy:
            return
        self._refresh_button.setEnabled(False)
        self._status.setText("正在读取包列表…")
        self._runner.submit(
            lambda: self._service.list(environment),
            on_done=lambda packages: self._on_packages(environment, packages),
            on_error=lambda error: self._on_packages_failed(environment, error),
        )

    def _on_packages(self, environment: Environment, packages: list[Package]) -> None:
        self._refresh_button.setEnabled(True)
        if not self._is_current(environment):
            return
        self._packages = packages
        self._model.set_packages(packages)
        self._status.setText(f"共 {len(packages)} 个包")
        self._update_buttons()

    def _on_packages_failed(self, environment: Environment, error: Exception) -> None:
        self._refresh_button.setEnabled(True)
        if not self._is_current(environment):
            return
        self._status.setText(f"读取失败：{error}")

    def _selected_package(self) -> Package | None:
        index = self._table.currentIndex()
        if not index.isValid():
            return None
        return self._model.package_at(self._proxy.mapToSource(index).row())

    def _update_buttons(self) -> None:
        environment = self._current_environment()
        available = (
            environment is not None and environment.available and not self._busy
        )
        self._install_button.setEnabled(available)
        self._uninstall_button.setEnabled(available and self._selected_package() is not None)

    def _install(self) -> None:
        environment = self._current_environment()
        specs = self._install_input.text().split()
        if environment is None or not specs:
            return
        self._install_input.clear()
        self._run_stream(
            "安装",
            lambda log: self._service.install(environment, specs, log),
        )

    def _uninstall(self) -> None:
        environment = self._current_environment()
        package = self._selected_package()
        if environment is None or package is None:
            return
        confirmed = QMessageBox.question(
            self,
            "卸载包",
            f"确定从「{environment.name}」卸载 {package.name} {package.version}？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._run_stream(
            "卸载",
            lambda log: self._service.uninstall(environment, package.name, log),
        )

    def _run_stream(self, action: str, work: Callable[[LineSink], None]) -> None:
        self._busy = True
        self._combo.setEnabled(False)
        self._refresh_button.setEnabled(False)
        self._install_button.setEnabled(False)
        self._uninstall_button.setEnabled(False)
        self._status.setText(f"正在{action}…")
        self._log.clear()
        self._runner.submit_stream(
            work,
            on_line=self._log.appendPlainText,
            on_done=lambda _result: self._on_stream_done(action),
            on_error=self._on_stream_failed,
        )

    def _on_stream_done(self, action: str) -> None:
        self._busy = False
        self._combo.setEnabled(True)
        self._refresh_button.setEnabled(True)
        self._status.setText(f"{action}完成")
        self._update_buttons()
        self._reload()

    def _on_stream_failed(self, error: Exception) -> None:
        self._busy = False
        self._combo.setEnabled(True)
        self._refresh_button.setEnabled(True)
        self._status.setText("操作失败")
        self._update_buttons()
        QMessageBox.critical(self, "操作失败", str(error))
