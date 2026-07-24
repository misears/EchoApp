"""
Echo Pro Recording UI Components
Reusable widgets for recording meters and transport controls.
"""

import os
import time

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
        self.peak_hold_timeout_sec = max(0.0, float(os.environ.get("ECHO_PEAK_HOLD_TIMEOUT_SEC", "2.0")))
        self.silence_threshold_db = float(os.environ.get("ECHO_SILENCE_WARN_DB", "-55.0"))
        self.last_clip_time = 0.0
        self.peak_hold_db = -80.0
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
        self.reset_button.clicked.connect(self.reset_meter_state)
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

    def reset_meter_state(self) -> None:
        self.clip_hold = False
        self.peak_hold_db = -80.0
        self.last_clip_time = 0.0
        self.peak_label.setText("-∞ dB")
        self._set_clip_visual(False)

    def update_levels(self, current_db: float, peak_db: float, clipping: bool = False) -> None:
        now = time.monotonic()
        self.meter.set_db(current_db)
        self.peak_hold_db = max(self.peak_hold_db, float(peak_db))
        self.peak_label.setText(f"{self.peak_hold_db:.1f} dB")
        if clipping:
            self.clip_hold = True
            self.last_clip_time = now
        elif self.clip_hold and self.peak_hold_timeout_sec > 0 and now - self.last_clip_time >= self.peak_hold_timeout_sec:
            self.clip_hold = False

        if current_db < self.silence_threshold_db and not self.clip_hold:
            self.clip_label.setText("SIL")
            self.clip_label.setStyleSheet("color: #f5c26b; font-weight: bold;")
            self.setStyleSheet("QFrame { border: 1px solid #a87f2f; background-color: #3a331f; }")
            return
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


class RecordingDiagnosticsWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.label = QLabel("Diagnostics: waiting")
        layout.addWidget(self.label)

    def update_diagnostics(self, diagnostics: dict) -> None:
        loop_cycles = int(diagnostics.get("loop_cycles_completed", 0))
        punch_starts = int(diagnostics.get("punch_start_hits", 0))
        punch_stops = int(diagnostics.get("punch_stop_hits", 0))
        auto_stops = int(diagnostics.get("auto_stop_events", 0))
        last_stop = int(diagnostics.get("last_auto_stop_sample", 0))
        last_error = str(diagnostics.get("last_transport_error", "")).strip()
        error_text = last_error if last_error else "none"
        self.label.setText(
            "Diag | "
            f"Loop cycles: {loop_cycles} | "
            f"Punch start/stop: {punch_starts}/{punch_stops} | "
            f"Auto stops: {auto_stops} @ {last_stop} | "
            f"Err: {error_text}"
        )
