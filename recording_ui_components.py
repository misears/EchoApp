"""
Echo Pro Recording UI Components
Reusable widgets for recording meters and transport controls.
"""

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QProgressBar, QWidget
except ImportError:  # pragma: no cover - optional UI dependency in lean environments
    Qt = type("Qt", (), {"AlignRight": 0, "AlignVCenter": 0})

    class QWidget:
        def __init__(self, *args, **kwargs):
            pass

    class QFrame(QWidget):
        StyledPanel = 0

        def setFrameShape(self, *args, **kwargs):
            pass

    class QHBoxLayout:
        def __init__(self, *args, **kwargs):
            pass

        def setContentsMargins(self, *args, **kwargs):
            pass

        def addWidget(self, *args, **kwargs):
            pass

    class QLabel(QWidget):
        def __init__(self, *args, **kwargs):
            pass

        def setMinimumWidth(self, *args, **kwargs):
            pass

        def setAlignment(self, *args, **kwargs):
            pass

        def setText(self, *args, **kwargs):
            pass

    class QPushButton(QWidget):
        def __init__(self, *args, **kwargs):
            pass

    class QProgressBar(QWidget):
        def __init__(self, *args, **kwargs):
            pass

        def setRange(self, *args, **kwargs):
            pass

        def setValue(self, *args, **kwargs):
            pass

        def setTextVisible(self, *args, **kwargs):
            pass

        def setMinimumHeight(self, *args, **kwargs):
            pass


class LevelMeter(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(0)
        self.setTextVisible(False)
        self.setMinimumHeight(14)

    def set_db(self, db_value: float) -> None:
        normalized = max(0.0, min(1.0, (db_value + 60.0) / 60.0))
        self.setValue(int(normalized * 100))


class TrackMeterWidget(QFrame):
    def __init__(self, track_name: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.clip_hold = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.label = QLabel(track_name)
        self.label.setMinimumWidth(120)
        layout.addWidget(self.label)

        self.meter = LevelMeter()
        layout.addWidget(self.meter)

        self.peak_label = QLabel("-∞ dB")
        self.peak_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.peak_label.setMinimumWidth(70)
        layout.addWidget(self.peak_label)

        self.clip_label = QLabel("OK")
        self.clip_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.clip_label.setMinimumWidth(40)
        layout.addWidget(self.clip_label)

        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_clip_hold)
        layout.addWidget(self.reset_button)

        self._set_clip_visual(False)

    def _set_clip_visual(self, clipped: bool) -> None:
        if clipped:
            self.clip_label.setText("CLIP")
            self.clip_label.setStyleSheet("color: #ff4d4d; font-weight: bold;")
            self.setStyleSheet("QFrame { border: 1px solid #ff4d4d; background-color: #3a1f1f; }")
        else:
            self.clip_label.setText("OK")
            self.clip_label.setStyleSheet("color: #9adf9a;")
            self.setStyleSheet("")

    def reset_clip_hold(self) -> None:
        self.clip_hold = False
        self._set_clip_visual(False)

    def update_levels(self, current_db: float, peak_db: float, clipping: bool = False) -> None:
        self.meter.set_db(current_db)
        self.peak_label.setText(f"{peak_db:.1f} dB")
        if clipping:
            self.clip_hold = True
        self._set_clip_visual(self.clip_hold)


class TransportBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.record_button = QPushButton("Record")
        self.stop_button = QPushButton("Stop")
        self.undo_button = QPushButton("Undo Take")
        self.redo_button = QPushButton("Redo Take")
        self.click_button = QPushButton("Metronome On")

        for button in [self.record_button, self.stop_button, self.undo_button, self.redo_button, self.click_button]:
            layout.addWidget(button)
