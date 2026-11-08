"""环境列表的表格模型与类型徽标绘制。"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from envarium.core.models import Environment, EnvKind
from envarium.ui.labels import KIND_LABELS
from envarium.ui.theme.tokens import Palette

KIND_ROLE = Qt.ItemDataRole.UserRole + 1
KIND_COLOR_ATTRS: dict[EnvKind, str] = {
    EnvKind.PYTHON: "accent",
    EnvKind.CONDA: "success",
    EnvKind.VENV: "warning",
}

HEADERS = ("名称", "类型", "Python 版本", "路径")
COLUMN_KIND = 1
_INVALID_INDEX = QModelIndex()


class EnvironmentTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._environments: list[Environment] = []

    def environment_at(self, row: int) -> Environment:
        return self._environments[row]

    def set_environments(self, environments: Sequence[Environment]) -> None:
        self.beginResetModel()
        self._environments = list(environments)
        self.endResetModel()

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
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            match column:
                case 0:
                    return environment.name
                case 1:
                    return ""  # 类型列由 KindBadgeDelegate 绘制
                case 2:
                    return environment.version or "—"
                case _:
                    return str(environment.path)
        if role == KIND_ROLE and column == COLUMN_KIND:
            return environment.kind
        if role == Qt.ItemDataRole.ToolTipRole:
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
