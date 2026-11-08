"""环境列表页：搜索筛选、异步统计、详情与环境管理操作。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QModelIndex, QPoint, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from envarium.core.errors import AppError
from envarium.core.models import (
    Environment,
    EnvironmentMetrics,
    EnvKind,
    ExportFormat,
    Package,
)
from envarium.infrastructure.config_store import AppConfig
from envarium.services.environment_service import EnvironmentService
from envarium.services.package_service import PackageService
from envarium.ui.dialogs import (
    CompareDialog,
    DeleteEnvironmentDialog,
    NewEnvironmentDialog,
)
from envarium.ui.labels import EXPORT_LABELS, KIND_LABELS
from envarium.ui.tasks import BackgroundRunner
from envarium.ui.theme.tokens import Palette
from envarium.ui.widgets.combo import ComboBox
from envarium.ui.widgets.detail_panel import DetailPanel
from envarium.ui.widgets.env_table import (
    COLUMN_KIND,
    SORT_ROLE,
    EnvironmentTableModel,
    KindBadgeDelegate,
)


def _version_branch(version: str) -> str:
    """版本筛选的粒度：主次版本，例如 3.12.4 -> 3.12。"""
    return ".".join(version.split(".")[:2])


class _EnvironmentFilter(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._needle = ""
        self._kind: EnvKind | None = None
        self._version = ""

    def set_needle(self, needle: str) -> None:
        self._needle = needle.strip().lower()
        self.invalidateFilter()

    def set_kind(self, kind: EnvKind | None) -> None:
        self._kind = kind
        self.invalidateFilter()

    def set_version(self, version: str) -> None:
        self._version = version
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        environment: Environment = self.sourceModel().environment_at(source_row)
        if self._kind is not None and environment.kind is not self._kind:
            return False
        if self._version and _version_branch(environment.version) != self._version:
            return False
        if not self._needle:
            return True
        return (
            self._needle in environment.name.lower()
            or self._needle in str(environment.path).lower()
        )


class EnvironmentsPage(QWidget):
    environments_changed = Signal(object)
    manage_packages_requested = Signal(object)

    def __init__(
        self,
        service: EnvironmentService,
        package_service: PackageService,
        runner: BackgroundRunner,
        config: AppConfig,
        palette: Palette,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._package_service = package_service
        self._runner = runner
        self._config = config
        self._palette = palette
        self._refreshing = False
        self._environments: list[Environment] = []
        self._current: Environment | None = None
        self._metrics: EnvironmentMetrics | None = None
        self._packages: list[Package] | None = None
        self._packages_error = ""
        self._busy: QProgressDialog | None = None

        self._model = EnvironmentTableModel(self)
        self._proxy = _EnvironmentFilter(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(SORT_ROLE)
        self._proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        title = QLabel("环境")
        title.setObjectName("PageTitle")

        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索名称或路径")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedWidth(220)

        self._kind_filter = ComboBox()
        self._kind_filter.addItem("全部类型", "")
        for kind in EnvKind:
            self._kind_filter.addItem(KIND_LABELS[kind], kind.value)

        self._version_filter = ComboBox()
        for combo in (self._kind_filter, self._version_filter):
            combo.setSizeAdjustPolicy(ComboBox.SizeAdjustPolicy.AdjustToContents)
            combo.setMinimumWidth(100)

        self._refresh_button = QPushButton("刷新")
        self._refresh_button.setObjectName("Primary")

        self._new_button = QPushButton("新建环境")
        self._add_button = QPushButton("添加已有环境")

        self._status = QLabel()
        self._status.setObjectName("StatusLabel")

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        toolbar.addWidget(self._search)
        toolbar.addWidget(self._kind_filter)
        toolbar.addWidget(self._version_filter)
        toolbar.addWidget(self._refresh_button)
        toolbar.addStretch(1)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.addWidget(self._new_button)
        action_row.addWidget(self._add_button)
        action_row.addStretch(1)
        action_row.addWidget(self._status)

        self._table = self._build_table(palette)
        self._empty = self._build_empty_state()
        self._stack = QStackedWidget()
        self._stack.addWidget(self._table)
        self._stack.addWidget(self._empty)

        self._detail = DetailPanel(self)
        self._build_actions()

        left = QVBoxLayout()
        left.setSpacing(12)
        left.addWidget(title)
        left.addLayout(toolbar)
        left.addLayout(action_row)
        left.addWidget(self._stack, 1)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)
        root.addLayout(left, 1)
        root.addWidget(self._detail)

        self._search.textChanged.connect(self._on_search_changed)
        self._kind_filter.currentIndexChanged.connect(self._on_kind_filter_changed)
        self._version_filter.currentIndexChanged.connect(self._on_version_filter_changed)
        self._refresh_button.clicked.connect(self.refresh)
        self._new_button.clicked.connect(self._create_environment)
        self._add_button.clicked.connect(self._add_environment)
        self._table.selectionModel().currentRowChanged.connect(
            self._on_current_row_changed
        )

        self.show_environments(self._service.cached())
        self._measure_all()
        self.refresh()

    def environments(self) -> list[Environment]:
        return list(self._environments)

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        delegate = self._table.itemDelegateForColumn(COLUMN_KIND)
        if isinstance(delegate, KindBadgeDelegate):
            delegate.set_palette(palette)
        self._table.viewport().update()

    def show_environments(self, environments: list[Environment]) -> None:
        self._environments = list(environments)
        self._model.set_environments(environments)
        self._rebuild_version_filter()
        self._update_count_status()
        self.environments_changed.emit(self._environments)
        self._restore_selection()
        self._sync_actions(self._current)
        self._stack.setCurrentWidget(self._table if environments else self._empty)

    def refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        self._refresh_button.setEnabled(False)
        self._set_status("正在扫描环境…")
        self._runner.submit(
            self._service.refresh,
            on_done=self._on_refreshed,
            on_error=self._on_refresh_failed,
        )

    def _build_table(self, palette: Palette) -> QTableView:
        table = QTableView()
        table.setModel(self._proxy)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(self._show_context_menu)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(36)
        table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        table.setItemDelegateForColumn(COLUMN_KIND, KindBadgeDelegate(palette, table))

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        for column in (1, 2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0, 140)
        table.setColumnWidth(1, 78)
        table.setColumnWidth(2, 88)
        table.setColumnWidth(3, 78)
        table.setColumnWidth(4, 110)
        table.setColumnWidth(5, 54)
        return table

    def _build_empty_state(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        empty_title = QLabel("还没有发现 Python 环境")
        empty_title.setObjectName("EmptyTitle")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_hint = QLabel(
            "点击「新建环境」创建 venv，或用「添加已有环境」纳入扫描范围外的环境；"
            "也可以在「设置」中添加 venv 扫描目录。"
        )
        empty_hint.setObjectName("EmptyHint")
        empty_hint.setWordWrap(True)
        empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_hint.setMaximumWidth(440)

        layout.addWidget(empty_title)
        layout.addWidget(empty_hint)
        return widget

    def _build_actions(self) -> None:
        self._terminal_action = self._make_action("打开终端", self._open_terminal)
        self._copy_path_action = self._make_action("复制路径", self._copy_path)
        self._packages_action = self._make_action("包管理", self._manage_packages)
        self._rename_action = self._make_action("重命名", self._rename_current)
        self._clone_action = self._make_action("克隆", self._clone_current)
        self._export_action = self._make_action("导出信息…", self._export_current)
        self._compare_action = self._make_action("环境对比…", self._compare_environments)
        self._delete_action = self._make_action("删除", self._delete_current, danger=True)
        self._forget_action = self._make_action("移除记录", self._forget_current)
        actions = [
            self._terminal_action,
            self._copy_path_action,
            self._packages_action,
            self._rename_action,
            self._clone_action,
            self._export_action,
            self._compare_action,
            self._delete_action,
            self._forget_action,
        ]
        self._actions = actions
        self._detail.set_actions(actions)

    def _make_action(
        self, text: str, slot: Callable[[], None], *, danger: bool = False
    ) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(slot)
        if danger:
            action.setProperty("danger", True)
        return action

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self._status.setText(text)
        self._status.setStyleSheet(f"color: {self._palette.danger};" if error else "")

    def _on_refreshed(self, environments: list[Environment]) -> None:
        self._refreshing = False
        self._refresh_button.setEnabled(True)
        self.show_environments(environments)
        self._measure_all()

    def _on_refresh_failed(self, error: Exception) -> None:
        self._refreshing = False
        self._refresh_button.setEnabled(True)
        self._set_status(f"扫描失败：{error}", error=True)

    def _measure_all(self) -> None:
        if not self._environments:
            return
        snapshot = list(self._environments)
        self._runner.submit(
            lambda: self._service.measure(snapshot),
            on_done=self._on_metrics_ready,
        )

    def _on_metrics_ready(self, metrics: dict[str, EnvironmentMetrics]) -> None:
        self._model.set_metrics(metrics)
        if self._current is None:
            return
        measured = metrics.get(self._current.key)
        if measured is not None:
            self._metrics = measured
            self._render_detail()

    def _rebuild_version_filter(self) -> None:
        """版本选项只来自当前类型下的环境，避免选出必然为空的条件。"""
        kind = self._selected_kind()
        previous = self._version_filter.currentData()
        versions = sorted(
            {
                _version_branch(environment.version)
                for environment in self._environments
                if environment.version
                and (kind is None or environment.kind is kind)
            }
        )
        self._version_filter.blockSignals(True)
        self._version_filter.clear()
        self._version_filter.addItem("全部版本", "")
        for version in versions:
            self._version_filter.addItem(version, version)
        index = self._version_filter.findData(previous)
        self._version_filter.setCurrentIndex(index if index >= 0 else 0)
        self._version_filter.blockSignals(False)
        self._proxy.set_version(self._version_filter.currentData() or "")

    def _selected_kind(self) -> EnvKind | None:
        value = self._kind_filter.currentData()
        return EnvKind(value) if value else None

    def _restore_selection(self) -> None:
        wanted = self._current.key if self._current is not None else ""
        for row in range(self._model.rowCount()):
            if self._model.environment_at(row).key != wanted:
                continue
            proxy_index = self._proxy.mapFromSource(self._model.index(row, 0))
            if proxy_index.isValid():
                self._table.selectRow(proxy_index.row())
                return
        if self._model.rowCount():
            self._table.selectRow(0)
        else:
            self._show_selection(None)

    def _on_kind_filter_changed(self, index: int) -> None:
        self._proxy.set_kind(self._selected_kind())
        self._rebuild_version_filter()
        self._update_count_status()

    def _on_version_filter_changed(self, index: int) -> None:
        self._proxy.set_version(self._version_filter.itemData(index) or "")
        self._update_count_status()

    def _on_search_changed(self, text: str) -> None:
        self._proxy.set_needle(text)
        self._update_count_status()

    def _update_count_status(self) -> None:
        total = len(self._environments)
        shown = self._proxy.rowCount()
        self._set_status(
            f"共 {total} 个环境" if shown == total else f"显示 {shown} / {total} 个环境"
        )

    def _on_current_row_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            self._show_selection(None)
            return
        source = self._proxy.mapToSource(current)
        self._show_selection(self._model.environment_at(source.row()))

    def _show_selection(self, environment: Environment | None) -> None:
        self._current = environment
        self._metrics = self._service.metrics(environment) if environment else None
        self._packages = None
        self._packages_error = ""
        self._sync_actions(environment)
        self._render_detail()
        if environment is None or not environment.available:
            return
        self._load_packages(environment)

    def _sync_actions(self, environment: Environment | None) -> None:
        has_selection = environment is not None
        usable = has_selection and environment.available
        self._terminal_action.setEnabled(usable)
        self._copy_path_action.setEnabled(has_selection)
        self._packages_action.setEnabled(usable)
        self._rename_action.setEnabled(usable and environment.renamable)
        self._clone_action.setEnabled(usable and environment.cloneable)
        self._export_action.setEnabled(usable)
        self._compare_action.setEnabled(len(self._environments) > 1)
        self._delete_action.setEnabled(usable and environment.removable)
        self._forget_action.setEnabled(has_selection and not environment.available)
        self._detail.sync_actions()

    def _render_detail(self) -> None:
        self._detail.show_environment(
            self._current,
            metrics=self._metrics,
            packages=self._packages,
            packages_error=self._packages_error,
        )

    def _is_current(self, environment: Environment) -> bool:
        return self._current is not None and self._current.key == environment.key

    def _load_packages(self, environment: Environment) -> None:
        self._runner.submit(
            lambda: self._package_service.list(environment),
            on_done=lambda packages: self._on_packages(environment, packages),
            on_error=lambda error: self._on_packages_failed(environment, error),
        )

    def _on_packages(self, environment: Environment, packages: list[Package]) -> None:
        if not self._is_current(environment):
            return
        self._packages = packages
        self._packages_error = ""
        self._render_detail()

    def _on_packages_failed(self, environment: Environment, error: Exception) -> None:
        if not self._is_current(environment):
            return
        self._packages = None
        self._packages_error = str(error)
        self._render_detail()

    def _show_context_menu(self, position: QPoint) -> None:
        index = self._table.indexAt(position)
        if index.isValid():
            self._table.selectRow(index.row())
        menu = QMenu(self)
        for action in self._actions:
            menu.addAction(action)
        menu.exec(self._table.viewport().mapToGlobal(position))

    def _open_terminal(self) -> None:
        if self._current is None:
            return
        try:
            self._service.open_terminal(self._current, self._config.terminal)
        except AppError as error:
            QMessageBox.warning(self, "无法打开终端", str(error))

    def _copy_path(self) -> None:
        if self._current is None:
            return
        QGuiApplication.clipboard().setText(str(self._current.path))

    def _manage_packages(self) -> None:
        if self._current is not None:
            self.manage_packages_requested.emit(self._current)

    def _create_environment(self) -> None:
        dialog = NewEnvironmentDialog(
            self._environments, self._service, self._runner, self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        request = dialog.request()
        self._run_operation(
            "正在创建环境…",
            lambda: self._service.create(request),
            on_done=lambda _result: self.refresh(),
        )

    def _add_environment(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择环境目录")
        if not directory:
            return
        self._run_operation(
            "正在添加环境…",
            lambda: self._service.add_manual(Path(directory)),
            on_done=lambda _result: self.refresh(),
        )

    def _rename_current(self) -> None:
        environment = self._current
        if environment is None:
            return
        name, accepted = QInputDialog.getText(
            self, "重命名环境", "新名称", text=environment.name
        )
        if not accepted or not name.strip():
            return
        if environment.kind is EnvKind.VENV:
            confirmed = QMessageBox.question(
                self,
                "重命名 venv",
                "venv 重命名只会修改目录名，内部记录的基础解释器路径不会更新，"
                "部分脚本可能失效。是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirmed != QMessageBox.StandardButton.Yes:
                return
        self._run_operation(
            "正在重命名环境…",
            lambda: self._service.rename(environment, name),
            on_done=lambda _result: self.refresh(),
        )

    def _clone_current(self) -> None:
        environment = self._current
        if environment is None:
            return
        name, accepted = QInputDialog.getText(
            self, "克隆环境", "新环境名称", text=f"{environment.name}-copy"
        )
        if not accepted or not name.strip():
            return
        self._run_operation(
            "正在克隆环境…",
            lambda: self._service.clone(environment, name),
            on_done=lambda _result: self.refresh(),
        )

    def _export_current(self) -> None:
        environment = self._current
        if environment is None:
            return
        formats = [ExportFormat.REQUIREMENTS, ExportFormat.JSON]
        if environment.kind is EnvKind.CONDA:
            formats.insert(1, ExportFormat.CONDA_ENV)
        target, selected = QFileDialog.getSaveFileName(
            self,
            "导出环境信息",
            str(Path.home() / f"{environment.name}-{formats[0].file_name}"),
            ";;".join(EXPORT_LABELS[item] for item in formats),
        )
        if not target:
            return
        export_format = next(
            (item for item in formats if EXPORT_LABELS[item] == selected), formats[0]
        )
        self._run_operation(
            "正在导出环境信息…",
            lambda: self._service.export(environment, Path(target), export_format),
        )

    def _compare_environments(self) -> None:
        dialog = CompareDialog(
            self._environments,
            self._service,
            self._runner,
            initial=self._current,
            parent=self,
        )
        dialog.exec()

    def _delete_current(self) -> None:
        environment = self._current
        if environment is None:
            return
        metrics = self._service.metrics(environment)
        if metrics is None:
            self._runner.submit(
                lambda: self._service.measure([environment]),
                on_done=lambda measured: self._confirm_delete(
                    environment, measured.get(environment.key)
                ),
                on_error=self._fail_operation,
            )
            return
        self._confirm_delete(environment, metrics)

    def _confirm_delete(
        self, environment: Environment, metrics: EnvironmentMetrics | None
    ) -> None:
        dialog = DeleteEnvironmentDialog(environment, metrics, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._run_operation(
            "正在删除环境…",
            lambda: self._service.remove(environment),
            on_done=lambda _result: self.refresh(),
        )

    def _forget_current(self) -> None:
        environment = self._current
        if environment is None:
            return
        self._run_operation(
            "正在移除记录…",
            lambda: self._service.forget(environment),
            on_done=lambda _result: self.refresh(),
        )

    def _run_operation(
        self,
        label: str,
        work: Callable[[], object],
        on_done: Callable[[object], None] | None = None,
    ) -> None:
        busy = QProgressDialog(self)
        busy.setWindowTitle("Envarium")
        busy.setLabelText(label)
        busy.setCancelButton(None)
        busy.setRange(0, 0)
        busy.setMinimumDuration(0)
        busy.setWindowModality(Qt.WindowModality.ApplicationModal)
        busy.setAutoClose(False)
        busy.setAutoReset(False)
        busy.show()
        self._busy = busy
        self._runner.submit(
            work,
            on_done=lambda result: self._finish_operation(result, on_done),
            on_error=self._fail_operation,
        )

    def _finish_operation(
        self, result: object, on_done: Callable[[object], None] | None
    ) -> None:
        self._close_busy()
        if on_done is not None:
            on_done(result)

    def _fail_operation(self, error: Exception) -> None:
        self._close_busy()
        QMessageBox.critical(self, "操作失败", str(error))

    def _close_busy(self) -> None:
        if self._busy is None:
            return
        self._busy.close()
        self._busy.deleteLater()
        self._busy = None
