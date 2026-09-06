from __future__ import annotations

LIGHT_QSS = """
QWidget { font-size: 13px; color: #1f2937; }
QMainWindow, QDialog { background: #eef1f4; }
QFrame#panel, QGroupBox {
    background: #ffffff;
    border: 1px solid #d7dde3;
    border-radius: 8px;
}
QGroupBox {
    font-weight: 600;
    margin-top: 12px;
    padding-top: 14px;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {
    background: #ffffff;
    border: 1px solid #cfd6dd;
    border-radius: 6px;
    padding: 5px 8px;
    min-height: 26px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
    border: 1px solid #0f766e;
}
QPushButton {
    background: #f8fafc;
    border: 1px solid #cfd6dd;
    border-radius: 6px;
    padding: 7px 12px;
}
QPushButton:hover { background: #eef2f6; }
QPushButton#primary {
    background: #0f766e;
    color: #ffffff;
    border: 1px solid #0f766e;
    font-weight: 600;
}
QPushButton#primary:hover { background: #0d9488; }
QPushButton#primary:disabled { background: #99b8b4; border-color: #99b8b4; }
QTableView {
    background: #ffffff;
    border: 1px solid #d7dde3;
    border-radius: 8px;
    gridline-color: #edf1f4;
    selection-background-color: #ccfbf1;
    selection-color: #134e4a;
    alternate-background-color: #f8fafc;
}
QHeaderView::section {
    background: #f3f5f7;
    border: none;
    border-bottom: 1px solid #d7dde3;
    padding: 7px 8px;
    font-weight: 600;
}
QProgressBar {
    border: 1px solid #d7dde3;
    border-radius: 6px;
    background: #ffffff;
    text-align: center;
    height: 16px;
}
QProgressBar::chunk { background: #0f766e; border-radius: 5px; }
QLabel#hint { color: #6b7280; }
QLabel#title { font-size: 18px; font-weight: 700; }
QLabel#empty { color: #6b7280; font-size: 14px; }
QStatusBar { background: #eef1f4; }
"""
