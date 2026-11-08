"""统一下拉框：弹出列表的行高、内边距与圆角选中样式。

Qt 的 QSS 对 QComboBox 弹出列表的 ``::item`` 不生效（Qt 6 实测），
因此列表项由委托自绘，使外观与主题令牌保持一致。
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, QSize, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QComboBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

_ROW_HEIGHT = 28
_TEXT_PADDING = 12
_INSET = 4
_RADIUS = 4
_VISIBLE_ROWS = 8


class _PopupItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        hint = super().sizeHint(option, index)
        return QSize(hint.width() + _TEXT_PADDING * 2, _ROW_HEIGHT)

    def paint(self, painter, option: QStyleOptionViewItem, index) -> None:
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        fill = option.palette.color(QPalette.ColorRole.Highlight)
        if selected or hovered:
            if not selected:
                fill.setAlphaF(0.45)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(
                QRectF(option.rect).adjusted(_INSET, 2, -_INSET, -2), _RADIUS, _RADIUS
            )

        text_option = QStyleOptionViewItem(option)
        self.initStyleOption(text_option, index)
        rect = text_option.rect.adjusted(_TEXT_PADDING, 0, -_TEXT_PADDING, 0)
        icon = text_option.icon
        if not icon.isNull():
            side = text_option.decorationSize.width() or 16
            icon.paint(
                painter, QRect(rect.left(), rect.center().y() - side // 2, side, side)
            )
            rect.adjust(side + 8, 0, 0, 0)

        painter.setPen(
            option.palette.color(
                QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
            )
        )
        text = text_option.fontMetrics.elidedText(
            text_option.text, Qt.TextElideMode.ElideRight, rect.width()
        )
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )
        painter.restore()


class ComboBox(QComboBox):
    """统一外观的下拉框。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setItemDelegate(_PopupItemDelegate(self))
        self.setMaxVisibleItems(_VISIBLE_ROWS)
