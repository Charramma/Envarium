"""主题应用：由调色板生成全局 QSS。"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from string import Template

from PySide6.QtWidgets import QApplication

from envarium.infrastructure.config_store import Theme
from envarium.ui.theme.tokens import DARK, TERMINAL, Palette, palette_for

_ASSETS = Path(__file__).resolve().parents[2] / "assets"

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
QLabel#DangerText {
    color: $danger;
    font-weight: 600;
}
QLabel#SectionTitle {
    font-weight: 600;
}
QDialog, QMessageBox, QProgressDialog {
    background: $window;
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
QPushButton#Danger {
    background: transparent;
    border: 1px solid $danger;
    color: $danger;
}
QPushButton#Danger:hover {
    background: $hover;
}
QLineEdit, QListWidget {
    background: $surface;
    border: 1px solid $border;
    border-radius: 6px;
    color: $text;
    padding: 6px 10px;
}
QComboBox {
    background: $surface;
    border: 1px solid $border;
    border-radius: 6px;
    color: $text;
    min-height: 18px;
    padding: 6px 10px;
    /* Fusion 默认用菜单式弹窗，会忽略 maxVisibleItems；0 表示改用列表式弹窗 */
    combobox-popup: 0;
}
QComboBox:hover {
    border: 1px solid $accent;
}
QComboBox:focus, QComboBox:on {
    border: 1px solid $accent;
}
QComboBox:disabled {
    background: $surface_alt;
    color: $text_secondary;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    background: transparent;
    border: none;
    width: 26px;
}
QComboBox::down-arrow {
    image: url("$chevron");
    width: 12px;
    height: 8px;
}
QLineEdit:focus {
    border: 1px solid $accent;
}
QPlainTextEdit {
    background: $surface_alt;
    border: 1px solid $border;
    border-radius: 6px;
    color: $text;
    padding: 6px;
}
QPlainTextEdit#RunLog {
    background: $terminal_background;
    border: 1px solid $terminal_border;
    border-radius: 6px;
    color: $terminal_foreground;
    padding: 6px;
}
QPlainTextEdit#RunLog QScrollBar::handle:vertical {
    background: $terminal_border;
}
QTabWidget::pane {
    border: 1px solid $border;
    border-radius: 6px;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: $text_secondary;
    padding: 7px 14px;
}
QTabBar::tab:selected {
    border-bottom: 2px solid $accent;
    color: $accent;
}
QMenuBar {
    background: $surface_alt;
    border-bottom: 1px solid $border;
    color: $text;
    padding: 0 8px;
}
QMenuBar::item {
    background: transparent;
    border-radius: 4px;
    padding: 3px 10px;
}
QMenuBar::item:selected {
    background: $hover;
}
QMenuBar::item:pressed {
    background: $accent_soft;
    color: $accent;
}
QMenu {
    background: $surface;
    border: 1px solid $border;
    padding: 4px;
}
QMenu::item {
    border-radius: 4px;
    padding: 6px 22px 6px 12px;
}
QMenu::item:selected {
    background: $accent_soft;
    color: $text;
}
QMenu::item:disabled {
    color: $text_secondary;
}
QComboBox QAbstractItemView {
    background: $surface;
    border: 0;
    color: $text;
    outline: 0;
    padding: 4px 0;
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
QFrame#DetailPanel, QFrame#RunLogPanel {
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
    chevron = _ASSETS / (
        "chevron-down-dark.svg" if palette is DARK else "chevron-down-light.svg"
    )
    tokens = {f"terminal_{name}": value for name, value in asdict(TERMINAL).items()}
    tokens["chevron"] = chevron.as_posix()
    return _QSS.substitute(asdict(palette) | tokens)


def apply_theme(app: QApplication, theme: Theme) -> None:
    app.setStyleSheet(build_stylesheet(palette_for(theme)))
