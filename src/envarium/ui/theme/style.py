"""主题应用：由调色板生成全局 QSS。"""

from __future__ import annotations

from dataclasses import asdict
from string import Template

from PySide6.QtWidgets import QApplication

from envarium.infrastructure.config_store import Theme
from envarium.ui.theme.tokens import Palette, palette_for

_QSS = Template(
    """
* {
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 13px;
}
QMainWindow, QWidget#Root {
    background: $window;
    color: $text;
}
QWidget#Sidebar {
    background: $surface_alt;
    border-right: 1px solid $border;
}
QLabel#AppTitle {
    font-size: 17px;
    font-weight: 600;
}
QLabel#AppSubtitle, QLabel#StatusLabel, QLabel#EmptyHint, QLabel#Hint,
QLabel#DetailKey, QLabel#VersionLabel {
    color: $text_secondary;
}
QLabel#PageTitle {
    font-size: 20px;
    font-weight: 600;
}
QLabel#DetailTitle {
    font-size: 15px;
    font-weight: 600;
}
QLabel#EmptyTitle {
    font-size: 15px;
    font-weight: 600;
}
QLabel#DetailValue {
    color: $text;
}
QPushButton[nav="true"] {
    background: transparent;
    border: none;
    border-radius: 6px;
    color: $text;
    padding: 9px 12px;
    text-align: left;
}
QPushButton[nav="true"]:hover {
    background: $hover;
}
QPushButton[nav="true"]:checked {
    background: $accent_soft;
    color: $accent;
    font-weight: 600;
}
QPushButton {
    background: $surface;
    border: 1px solid $border;
    border-radius: 6px;
    color: $text;
    padding: 6px 14px;
}
QPushButton:hover {
    background: $hover;
}
QPushButton:disabled {
    color: $text_secondary;
}
QPushButton#Primary {
    background: $accent;
    border: none;
    color: #ffffff;
}
QPushButton#Primary:hover {
    background: $accent_hover;
}
QLineEdit, QComboBox, QListWidget {
    background: $surface;
    border: 1px solid $border;
    border-radius: 6px;
    color: $text;
    padding: 6px 10px;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid $accent;
}
QComboBox QAbstractItemView {
    background: $surface;
    border: 1px solid $border;
    selection-background-color: $accent_soft;
    selection-color: $text;
}
QTableView {
    background: $surface;
    border: 1px solid $border;
    border-radius: 8px;
    color: $text;
    alternate-background-color: $surface_alt;
    gridline-color: $border;
    selection-background-color: $accent_soft;
    selection-color: $text;
    outline: none;
}
QTableView::item {
    padding-left: 10px;
    padding-right: 6px;
}
QHeaderView::section {
    background: $surface_alt;
    border: none;
    border-bottom: 1px solid $border;
    color: $text_secondary;
    padding: 8px;
}
QFrame#DetailPanel {
    background: $surface;
    border: 1px solid $border;
    border-radius: 8px;
}
QFrame#Separator {
    background: $border;
    border: none;
    max-height: 1px;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: $border;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""
)


def build_stylesheet(palette: Palette) -> str:
    return _QSS.substitute(asdict(palette))


def apply_theme(app: QApplication, theme: Theme) -> None:
    app.setStyleSheet(build_stylesheet(palette_for(theme)))
