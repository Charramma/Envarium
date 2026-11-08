"""环境创建与破坏性操作确认对话框。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from envarium.core.errors import AppError, ErrorKind
from envarium.core.models import Environment, EnvironmentMetrics, PackageDiff
from envarium.services.environment_service import CondaRequest, EnvironmentService, VenvRequest
from envarium.ui.formatting import format_size
from envarium.ui.labels import KIND_LABELS
from envarium.ui.tasks import BackgroundRunner


class NewEnvironmentDialog(QDialog):
    """收集创建 venv / conda 环境所需的输入。"""

    def __init__(
        self, environments: Sequence[Environment], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建环境")
        self.setMinimumWidth(500)
        self._request: VenvRequest | CondaRequest | None = None

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_venv_tab(environments), "venv 虚拟环境")
        self._tabs.addTab(self._build_conda_tab(), "conda 环境")

        buttons = QDialogButtonBox()
        create = buttons.addButton("创建", QDialogButtonBox.ButtonRole.AcceptRole)
        create.setObjectName("Primary")
        buttons.addButton("取消", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(self._tabs)
        layout.addWidget(buttons)

    def request(self) -> VenvRequest | CondaRequest:
        assert self._request is not None
        return self._request

    def accept(self) -> None:
        try:
            self._request = self._build_request()
        except AppError as error:
            QMessageBox.warning(self, "无法创建", str(error))
            return
        super().accept()

    def _build_venv_tab(self, environments: Sequence[Environment]) -> QWidget:
        tab = QWidget()
        layout = QGridLayout(tab)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)
        layout.setColumnStretch(1, 1)

        self._base_combo = QComboBox()
        for environment in environments:
            version = environment.version or "未知版本"
            self._base_combo.addItem(
                f"{environment.name} · {version}", str(environment.interpreter)
            )
        if self._base_combo.count() == 0:
            self._base_combo.addItem("未发现可用的 Python 解释器", "")

        self._target_edit = QLineEdit()
        self._target_edit.setPlaceholderText(r"例如 D:\venvs\my-project")
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._choose_target)
        target_row = QHBoxLayout()
        target_row.setSpacing(8)
        target_row.addWidget(self._target_edit, 1)
        target_row.addWidget(browse)

        self._system_site = QCheckBox("允许访问基础解释器的全局 site-packages")

        hint = QLabel("创建完成后会自动加入环境库。")
        hint.setObjectName("Hint")

        layout.addWidget(QLabel("基础解释器"), 0, 0)
        layout.addWidget(self._base_combo, 0, 1)
        layout.addWidget(QLabel("目标目录"), 1, 0)
        layout.addLayout(target_row, 1, 1)
        layout.addWidget(self._system_site, 2, 1)
        layout.addWidget(hint, 3, 1)
        return tab

    def _build_conda_tab(self) -> QWidget:
        tab = QWidget()
        layout = QGridLayout(tab)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)
        layout.setColumnStretch(1, 1)

        self._conda_name = QLineEdit()
        self._conda_name.setPlaceholderText("例如 data-science")
        self._conda_version = QLineEdit()
        self._conda_version.setPlaceholderText("留空使用最新版本，例如 3.12")

        hint = QLabel("环境将创建在 conda 的 envs 目录下，由 conda 下载并安装指定版本。")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)

        layout.addWidget(QLabel("环境名称"), 0, 0)
        layout.addWidget(self._conda_name, 0, 1)
        layout.addWidget(QLabel("Python 版本"), 1, 0)
        layout.addWidget(self._conda_version, 1, 1)
        layout.addWidget(hint, 2, 1)
        return tab

    def _choose_target(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择 venv 目标目录")
        if directory:
            self._target_edit.setText(directory)

    def _build_request(self) -> VenvRequest | CondaRequest:
        if self._tabs.currentIndex() == 0:
            interpreter = self._base_combo.currentData()
            if not interpreter:
                raise AppError(
                    "未发现可用的基础解释器，请先安装 Python 或 conda。",
                    kind=ErrorKind.INVALID,
                )
            raw_target = self._target_edit.text().strip()
            if not raw_target:
                raise AppError("请填写目标目录。", kind=ErrorKind.INVALID)
            target = Path(raw_target)
            if not target.is_absolute():
                raise AppError("目标目录必须是绝对路径。", kind=ErrorKind.INVALID)
            return VenvRequest(
                interpreter=Path(interpreter),
                target=target,
                system_site_packages=self._system_site.isChecked(),
            )
        name = self._conda_name.text().strip()
        if not name:
            raise AppError("请填写 conda 环境名称。", kind=ErrorKind.INVALID)
        return CondaRequest(name=name, python_version=self._conda_version.text().strip())


class DeleteEnvironmentDialog(QDialog):
    """删除前的二次确认：明确展示路径、类型与占用空间。"""

    def __init__(
        self,
        environment: Environment,
        metrics: EnvironmentMetrics | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("删除环境")
        self.setMinimumWidth(480)

        warning = QLabel("该环境目录将被永久删除，且无法恢复。")
        warning.setObjectName("DangerText")
        warning.setWordWrap(True)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)
        rows = [
            ("名称", environment.name),
            ("类型", KIND_LABELS[environment.kind]),
            ("环境路径", str(environment.path)),
            ("占用空间", format_size(metrics.size_bytes) if metrics else "统计中…"),
        ]
        for row, (key, value) in enumerate(rows):
            key_label = QLabel(key)
            key_label.setObjectName("DetailKey")
            value_label = QLabel(value)
            value_label.setObjectName("DetailValue")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value_label, row, 1)

        buttons = QDialogButtonBox()
        buttons.addButton("取消", QDialogButtonBox.ButtonRole.RejectRole)
        delete = buttons.addButton("删除", QDialogButtonBox.ButtonRole.AcceptRole)
        delete.setObjectName("Danger")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(warning)
        layout.addLayout(grid)
        layout.addWidget(buttons)


class CompareDialog(QDialog):
    """两个环境的包差异对比。"""

    _HEADERS = ("包名", "左侧版本", "右侧版本", "状态")

    def __init__(
        self,
        environments: Sequence[Environment],
        service: EnvironmentService,
        runner: BackgroundRunner,
        *,
        initial: Environment | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("环境对比")
        self.resize(720, 520)
        self._service = service
        self._runner = runner
        self._environments = {environment.key: environment for environment in environments}
        self._diffs: list[PackageDiff] = []
        self._loading = False

        keys = list(self._environments)
        left_key = initial.key if initial is not None else keys[0]
        right_key = next((key for key in keys if key != left_key), left_key)

        self._left_combo = self._make_combo(left_key)
        self._right_combo = self._make_combo(right_key)

        picker = QHBoxLayout()
        picker.setSpacing(8)
        picker.addWidget(QLabel("左侧"))
        picker.addWidget(self._left_combo, 1)
        picker.addWidget(QLabel("右侧"))
        picker.addWidget(self._right_combo, 1)

        self._only_diff = QCheckBox("仅显示差异")
        self._only_diff.setChecked(True)
        self._status = QLabel()
        self._status.setObjectName("Hint")

        self._table = QTableWidget(0, len(self._HEADERS))
        self._table.setHorizontalHeaderLabels(self._HEADERS)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for column in (1, 2, 3):
            self._table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )

        buttons = QDialogButtonBox()
        buttons.addButton("关闭", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addLayout(picker)
        layout.addWidget(self._only_diff)
        layout.addWidget(self._table, 1)
        layout.addWidget(self._status)
        layout.addWidget(buttons)

        self._left_combo.currentIndexChanged.connect(self._reload)
        self._right_combo.currentIndexChanged.connect(self._reload)
        self._only_diff.toggled.connect(self._apply_filter)
        self._reload()

    def _make_combo(self, selected_key: str) -> QComboBox:
        combo = QComboBox()
        for environment in self._environments.values():
            version = environment.version or "未知版本"
            combo.addItem(f"{environment.name} · {version}", environment.key)
        combo.setCurrentIndex(max(0, combo.findData(selected_key)))
        return combo

    def _reload(self) -> None:
        left = self._environments.get(self._left_combo.currentData())
        right = self._environments.get(self._right_combo.currentData())
        if left is None or right is None or self._loading:
            return
        if left.key == right.key:
            self._diffs = []
            self._status.setText("请选择两个不同的环境。")
            self._populate()
            return
        self._loading = True
        self._status.setText("正在读取包列表…")
        self._left_combo.setEnabled(False)
        self._right_combo.setEnabled(False)
        self._runner.submit(
            lambda: self._service.compare(left, right),
            on_done=self._on_compared,
            on_error=self._on_compare_failed,
        )

    def _on_compared(self, diffs: list[PackageDiff]) -> None:
        self._loading = False
        self._left_combo.setEnabled(True)
        self._right_combo.setEnabled(True)
        self._diffs = diffs
        self._populate()

    def _on_compare_failed(self, error: Exception) -> None:
        self._loading = False
        self._left_combo.setEnabled(True)
        self._right_combo.setEnabled(True)
        self._diffs = []
        self._populate()
        self._status.setText(f"对比失败：{error}")

    def _populate(self) -> None:
        self._table.setRowCount(len(self._diffs))
        for row, diff in enumerate(self._diffs):
            cells = (
                diff.name,
                diff.left_version or "—",
                diff.right_version or "—",
                self._diff_label(diff),
            )
            for column, text in enumerate(cells):
                self._table.setItem(row, column, QTableWidgetItem(text))
        if self._diffs:
            differences = sum(1 for diff in self._diffs if diff.differs)
            self._status.setText(f"共 {len(self._diffs)} 个包，{differences} 处版本差异")
        self._apply_filter()

    def _apply_filter(self) -> None:
        only_diff = self._only_diff.isChecked()
        for row, diff in enumerate(self._diffs):
            self._table.setRowHidden(row, only_diff and not diff.differs)

    @staticmethod
    def _diff_label(diff: PackageDiff) -> str:
        if not diff.right_version:
            return "仅左侧"
        if not diff.left_version:
            return "仅右侧"
        return "版本不同" if diff.differs else "相同"
