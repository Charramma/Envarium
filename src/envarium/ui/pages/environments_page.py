"""环境列表页：搜索、筛选、列表与详情。"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from envarium.core.models import Environment, EnvKind
from envarium.services.environment_service import EnvironmentService
from envarium.ui.labels import KIND_LABELS
from envarium.ui.tasks import BackgroundRunner
from envarium.ui.theme.tokens import Palette
from envarium.ui.widgets.detail_panel import DetailPanel
from envarium.ui.widgets.env_table import COLUMN_KIND, EnvironmentTableModel, KindBadgeDelegate


class _EnvironmentFilter(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._needle = ""
        self._kind: EnvKind | None = None

    def set_needle(self, needle: str) -> None:
        self._needle = needle.strip().lower()
        self.invalidateFilter()

    def set_kind(self, kind: EnvKind | None) -> None:
        self._kind = kind
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        environment: Environment = self.sourceModel().environment_at(source_row)
        if self._kind is not None and environment.kind is not self._kind:
            return False
        if not self._needle:
            return True
        return (
            self._needle in environment.name.lower()
            or self._needle in str(environment.path).lower()
        )


class EnvironmentsPage(QWidget):
    def __init__(
        self,
        service: EnvironmentService,
        runner: BackgroundRunner,
        palette: Palette,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._runner = runner
        self._palette = palette
        self._refreshing = False

        self._model = EnvironmentTableModel(self)
        self._proxy = _EnvironmentFilter(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        title = QLabel("环境")
        title.setObjectName("PageTitle")

        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索名称或路径")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedWidth(260)

        self._kind_filter = QComboBox()
        self._kind_filter.addItem("全部类型", None)
        for kind in EnvKind:
            self._kind_filter.addItem(KIND_LABELS[kind], kind)
        self._kind_filter.setFixedWidth(120)

        self._refresh_button = QPushButton("刷新")
        self._refresh_button.setObjectName("Primary")

        self._status = QLabel()
        self._status.setObjectName("StatusLabel")

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        toolbar.addWidget(self._search)
        toolbar.addWidget(self._kind_filter)
        toolbar.addWidget(self._refresh_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self._status)

        self._table = self._build_table(palette)
        self._empty = self._build_empty_state()
        self._stack = QStackedWidget()
        self._stack.addWidget(self._table)
        self._stack.addWidget(self._empty)

        self._detail = DetailPanel(self)

        left = QVBoxLayout()
        left.setSpacing(12)
        left.addWidget(title)
        left.addLayout(toolbar)
        left.addWidget(self._stack, 1)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)
        root.addLayout(left, 1)
        root.addWidget(self._detail)

        self._search.textChanged.connect(self._proxy.set_needle)
        self._kind_filter.currentIndexChanged.connect(self._on_kind_filter_changed)
        self._refresh_button.clicked.connect(self.refresh)
        self._table.selectionModel().currentRowChanged.connect(
            self._on_current_row_changed
        )
        self._model.modelReset.connect(self._sync_empty_state)

        self.show_environments(self._service.cached())
        self.refresh()

    def _build_table(self, palette: Palette) -> QTableView:
        table = QTableView()
        table.setModel(self._proxy)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(36)
        table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        table.setItemDelegateForColumn(COLUMN_KIND, KindBadgeDelegate(palette, table))

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0, 190)
        table.setColumnWidth(1, 92)
        table.setColumnWidth(2, 104)
        return table

    def _build_empty_state(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        empty_title = QLabel("还没有发现 Python 环境")
        empty_title.setObjectName("EmptyTitle")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_hint = QLabel("安装 Python 后点击「刷新」；已有 venv 可在「设置」中添加扫描目录。")
        empty_hint.setObjectName("EmptyHint")
        empty_hint.setWordWrap(True)
        empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_hint.setMaximumWidth(420)

        layout.addWidget(empty_title)
        layout.addWidget(empty_hint)
        return widget

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        delegate = self._table.itemDelegateForColumn(COLUMN_KIND)
        if isinstance(delegate, KindBadgeDelegate):
            delegate.set_palette(palette)
        self._table.viewport().update()

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self._status.setText(text)
        self._status.setStyleSheet(f"color: {self._palette.danger};" if error else "")

    def show_environments(self, environments: list[Environment]) -> None:
        self._model.set_environments(environments)
        self._set_status(f"共 {len(environments)} 个环境")
        if environments:
            self._table.selectRow(0)
        else:
            self._detail.show_environment(None)

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

    def _on_refreshed(self, environments: list[Environment]) -> None:
        self._refreshing = False
        self._refresh_button.setEnabled(True)
        self.show_environments(environments)

    def _on_refresh_failed(self, error: Exception) -> None:
        self._refreshing = False
        self._refresh_button.setEnabled(True)
        self._set_status(f"扫描失败：{error}", error=True)

    def _on_kind_filter_changed(self, index: int) -> None:
        self._proxy.set_kind(self._kind_filter.itemData(index))

    def _on_current_row_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            self._detail.show_environment(None)
            return
        source = self._proxy.mapToSource(current)
        self._detail.show_environment(self._model.environment_at(source.row()))

    def _sync_empty_state(self) -> None:
        has_environments = self._model.rowCount() > 0
        self._stack.setCurrentWidget(self._table if has_environments else self._empty)
