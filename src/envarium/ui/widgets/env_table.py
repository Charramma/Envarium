"""环境列表的表格模型与类型徽标绘制。"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from envarium.core.models import Environment, EnvironmentMetrics, EnvKind
from envarium.ui.formatting import format_size, format_time
from envarium.ui.labels import KIND_LABELS
from envarium.ui.theme.tokens import Palette

KIND_ROLE = Qt.ItemDataRole.UserRole + 1
SORT_ROLE = Qt.ItemDataRole.UserRole + 2
KIND_COLOR_ATTRS: dict[EnvKind, str] = {
    EnvKind.PYTHON: "accent",
    EnvKind.CONDA: "success",
    EnvKind.VENV: "warning",
}

HEADERS = ("名称", "类型", "Python 版本", "大小", "修改时间", "状态", "路径")
COLUMN_KIND = 1
COLUMN_VERSION = 2
COLUMN_SIZE = 3
COLUMN_MODIFIED = 4
COLUMN_STATUS = 5
_INVALID_INDEX = QModelIndex()


def _version_sort_key(version: str) -> str:
    """把 3.13.5 转成可比较的定长字符串，避免 3.9 排在 3.13 之后。"""
    parts: list[str] = []
    for part in version.split(".")[:3]:
        digits = "".join(char for char in part if char.isdigit())
        parts.append(f"{int(digits):04d}" if digits else "0000")
    return ".".join(parts)


class EnvironmentTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._environments: list[Environment] = []
        self._metrics: dict[str, EnvironmentMetrics] = {}

    def environment_at(self, row: int) -> Environment:
        return self._environments[row]

    def set_environments(self, environments: Sequence[Environment]) -> None:
        self.beginResetModel()
        self._environments = list(environments)
        self.endResetModel()

    def set_metrics(self, metrics: dict[str, EnvironmentMetrics]) -> None:
        self._metrics = dict(metrics)
        if not self._environments:
            return
        self.dataChanged.emit(
            self.index(0, COLUMN_SIZE),
            self.index(len(self._environments) - 1, COLUMN_MODIFIED),
            [Qt.ItemDataRole.DisplayRole, SORT_ROLE],
        )

    def rowCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:
        return 0 if parent.isValid() else len(self._environments)

    def columnCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = 0):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = 0):
        if not index.isValid():
            return None
        environment = self._environments[index.row()]
        metrics = self._metrics.get(environment.key)
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return environment.name
            if column == COLUMN_KIND:
                return ""  # 类型列由 KindBadgeDelegate 绘制
            if column == COLUMN_VERSION:
                return environment.version or "—"
            if column == COLUMN_SIZE:
                return format_size(metrics.size_bytes) if metrics else "—"
            if column == COLUMN_MODIFIED:
                return format_time(metrics.modified_at) if metrics else "—"
            if column == COLUMN_STATUS:
                if not environment.available:
                    return "已失效"
                return "当前" if environment.on_path else ""
            return str(environment.path)

        if role == SORT_ROLE:
            if column == 0:
                return environment.name.lower()
            if column == COLUMN_VERSION:
                return _version_sort_key(environment.version)
            if column == COLUMN_SIZE:
                return metrics.size_bytes if metrics else -1
            if column == COLUMN_MODIFIED:
                return metrics.modified_at.timestamp() if metrics else 0.0
            if column == COLUMN_STATUS:
                return "" if environment.available else "0"
            return str(environment.path).lower()

        if role == KIND_ROLE and column == COLUMN_KIND:
            return environment.kind
        if role == Qt.ItemDataRole.ToolTipRole:
            if column == COLUMN_STATUS and not environment.available:
                return "环境路径已不存在，可右键移除记录"
            return str(environment.path)
        return None


class KindBadgeDelegate(QStyledItemDelegate):
    """把环境类型绘制为圆角徽标。"""

    def __init__(self, palette: Palette, parent=None) -> None:
        super().__init__(parent)
        self._palette = palette

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        kind = index.data(KIND_ROLE)
        if kind is None:
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(self._palette.accent_soft))
        elif option.features & QStyleOptionViewItem.ViewItemFeature.Alternate:
            painter.fillRect(option.rect, QColor(self._palette.surface_alt))

        text = KIND_LABELS[kind]
        color = QColor(getattr(self._palette, KIND_COLOR_ATTRS[kind]))
        background = QColor(color)
        background.setAlpha(32)

        metrics = QFontMetrics(option.font)
        badge = QRectF(
            option.rect.x() + 8,
            option.rect.center().y() - (metrics.height() + 8) / 2,
            metrics.horizontalAdvance(text) + 20,
            metrics.height() + 8,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(badge, badge.height() / 2, badge.height() / 2)
        painter.setPen(QPen(color))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)

        painter.setPen(QPen(QColor(self._palette.border)))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.restore()
