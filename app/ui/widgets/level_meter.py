from PySide6.QtCore import Qt
from PySide6.QtWidgets import QProgressBar


class LevelMeterBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(0)
        self.setTextVisible(False)
        self.setFixedHeight(7)

    def set_db(self, db_value: float) -> None:
        normalized = max(0.0, min(1.0, (db_value + 60.0) / 60.0))
        self.setValue(int(normalized * 100))


class VerticalLevelMeter(QProgressBar):
    """Narrow vertical level meter for L/R stereo display inside a channel strip."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(0)
        self.setTextVisible(False)
        self.setOrientation(Qt.Orientation.Vertical)
        self.setFixedWidth(10)
        self.setMinimumHeight(60)
        self.setStyleSheet(
            "QProgressBar:vertical { border:1px solid #0f3460; border-radius:3px; background:#0d1b2a; }"
            "QProgressBar::chunk:vertical { background: qlineargradient(x1:0,y1:1,x2:0,y2:0,"
            "stop:0 #22aa22, stop:0.7 #aaaa00, stop:1 #ee2222); border-radius:2px; }"
        )

    def set_db(self, db_value: float) -> None:
        normalized = max(0.0, min(1.0, (db_value + 60.0) / 60.0))
        self.setValue(int(normalized * 100))
