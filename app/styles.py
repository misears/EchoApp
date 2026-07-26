DARK_STYLE = """
QMainWindow, QDialog, QWidget {
    background-color: #16213e;
    color: #dde1e7;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 11px;
}
QTabWidget::pane {
    border: 1px solid #0f3460;
    background: #1a1a2e;
    border-radius: 4px;
}
QTabBar::tab {
    background: #0f3460;
    color: #aab4be;
    padding: 8px 18px;
    margin-right: 2px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background: #e94560;
    color: #ffffff;
}
QPushButton {
    background-color: #0f3460;
    color: #dde1e7;
    border: 1px solid #1a4080;
    padding: 5px 12px;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #1a4080;
    border-color: #e94560;
}
QPushButton:pressed {
    background-color: #e94560;
    color: #ffffff;
}
QLineEdit, QTextEdit, QListWidget, QComboBox {
    background-color: #0d1b2a;
    color: #dde1e7;
    border: 1px solid #0f3460;
    border-radius: 4px;
    selection-background-color: #e94560;
}
QGroupBox {
    border: 1px solid #1a4080;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: #e94560;
    font-weight: bold;
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: #0d1b2a; width: 8px; border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #0f3460; border-radius: 4px; min-height: 20px;
}
QScrollBar:horizontal {
    background: #0d1b2a; height: 8px; border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #0f3460; border-radius: 4px; min-width: 20px;
}
QStatusBar {
    background-color: #0a1020;
    color: #aab4be;
    border-top: 1px solid #0f3460;
}
QPushButton[channelBtn="punch"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #c07000, stop:0.45 #e09010, stop:0.55 #b06000, stop:1 #803000);
    color: #fff8e0;
    border: 1px solid #a05000;
    border-bottom: 3px solid #501800;
    border-radius: 4px;
    font-weight: bold;
    padding: 3px 6px;
}
QPushButton[channelBtn="punch"]:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ff9900, stop:1 #cc6600);
    border-bottom: 1px solid #501800;
    border-top: 3px solid #501800;
}
QPushButton[channelBtn="mute"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3a6090, stop:0.45 #4a80b0, stop:0.55 #2a5080, stop:1 #1a3060);
    color: #d0e8ff;
    border: 1px solid #2a5080;
    border-bottom: 3px solid #0a1840;
    border-radius: 4px;
    font-weight: bold;
    padding: 3px 6px;
}
QPushButton[channelBtn="mute"]:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e94560, stop:1 #a02040);
    border-bottom: 1px solid #0a1840;
    border-top: 3px solid #0a1840;
    color: #ffffff;
}
QPushButton[channelBtn="solo"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #206020, stop:0.45 #308030, stop:0.55 #185018, stop:1 #0e3010);
    color: #c8ffc8;
    border: 1px solid #185018;
    border-bottom: 3px solid #061806;
    border-radius: 4px;
    font-weight: bold;
    padding: 3px 6px;
}
QPushButton[channelBtn="solo"]:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #40e040, stop:1 #20a020);
    border-bottom: 1px solid #061806;
    border-top: 3px solid #061806;
    color: #000000;
}
QSplitter::handle {
    background: #0f3460;
}
QSplitter::handle:vertical {
    height: 5px;
}
QSplitter::handle:hover {
    background: #e94560;
}
"""
