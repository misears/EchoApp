"""
Echo Pro Recording UI Components
Reusable widgets for recording meters and transport controls.
"""

import os
import time
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QComboBox,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QPushButton,
        QProgressBar,
        QVBoxLayout,
        QWidget,
    )

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QComboBox,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QPushButton,
        QProgressBar,
        QVBoxLayout,
        QWidget,
    )
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

        def addLayout(self, *args, **kwargs):
            pass

    class QVBoxLayout(QHBoxLayout):
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

        def setCheckable(self, *args, **kwargs):
            pass

    class QLineEdit(QWidget):
        def __init__(self, *args, **kwargs):
            pass

        def setPlaceholderText(self, *args, **kwargs):
            pass

    class QComboBox(QWidget):
        def __init__(self, *args, **kwargs):
            pass

        def addItem(self, *args, **kwargs):
            pass

    class QListWidget(QWidget):
        def __init__(self, *args, **kwargs):
            pass

        def addItem(self, *args, **kwargs):
            pass

        def clear(self):
            pass

        def setMaximumHeight(self, *args, **kwargs):
            pass

    class QListWidgetItem:
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
        clip_events = int(diagnostics.get("clip_events_total", 0))
        silence_warnings = int(diagnostics.get("silence_warnings_active", 0))
        last_error = str(diagnostics.get("last_transport_error", "")).strip()
        error_text = last_error if last_error else "none"
        self.label.setText(
            "Diag | "
            f"Loop cycles: {loop_cycles} | "
            f"Punch start/stop: {punch_starts}/{punch_stops} | "
            f"Auto stops: {auto_stops} @ {last_stop} | "
            f"Clip events: {clip_events} | "
            f"Silence warn: {silence_warnings} | "
            f"Err: {error_text}"
        )


class TakeListWidget(QFrame):
    """Reusable track-scoped take list with deterministic callback wiring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self._view_mode = "expanded"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

    def clear(self) -> None:
        self.list_widget.clear()

    def add_take_row(self, text: str, data: Optional[dict] = None) -> None:
        item = QListWidgetItem(text)
        if data is not None:
            item.setData(Qt.ItemDataRole.UserRole, data)
        self.list_widget.addItem(item)

    def add_placeholder(self, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.list_widget.addItem(item)

    def current_data(self) -> Optional[dict]:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, dict) else None

    def on_item_double_clicked(self, callback: Callable) -> None:
        self.list_widget.itemDoubleClicked.connect(callback)

    def set_view_mode(self, mode: str) -> None:
        mode_value = str(mode).strip().lower()
        self._view_mode = "compact" if mode_value == "compact" else "expanded"
        # Compact mode keeps the panel usable on small screens.
        if self._view_mode == "compact":
            self.list_widget.setMaximumHeight(120)
        else:
            self.list_widget.setMaximumHeight(16777215)

    def get_view_mode(self) -> str:
        return self._view_mode


class TransportPunchLoopWidget(QFrame):
    """Encapsulated punch/loop transport controls with shared field handles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)

        self.pre_roll_bar_input = QLineEdit()
        self.pre_roll_bar_input.setPlaceholderText("Pre-Roll (bars)")
        layout.addWidget(self.pre_roll_bar_input)

        self.post_roll_bar_input = QLineEdit()
        self.post_roll_bar_input.setPlaceholderText("Post-Roll (bars)")
        layout.addWidget(self.post_roll_bar_input)

        self.set_roll_btn = QPushButton("Set Pre/Post")
        layout.addWidget(self.set_roll_btn)

        self.punch_mode_combo = QComboBox()
        self.punch_mode_combo.addItem("Punch Off", False)
        self.punch_mode_combo.addItem("Punch On", True)
        layout.addWidget(self.punch_mode_combo)

        self.punch_in_bar_input = QLineEdit()
        self.punch_in_bar_input.setPlaceholderText("Punch In (bars)")
        layout.addWidget(self.punch_in_bar_input)

        self.punch_out_bar_input = QLineEdit()
        self.punch_out_bar_input.setPlaceholderText("Punch Out (bars)")
        layout.addWidget(self.punch_out_bar_input)

        self.set_punch_btn = QPushButton("Set Punch")
        layout.addWidget(self.set_punch_btn)

        self.loop_mode_combo = QComboBox()
        self.loop_mode_combo.addItem("Loop Off", False)
        self.loop_mode_combo.addItem("Loop On", True)
        layout.addWidget(self.loop_mode_combo)

        self.loop_start_bar_input = QLineEdit()
        self.loop_start_bar_input.setPlaceholderText("Loop Start (bars)")
        layout.addWidget(self.loop_start_bar_input)

        self.loop_end_bar_input = QLineEdit()
        self.loop_end_bar_input.setPlaceholderText("Loop End (bars)")
        layout.addWidget(self.loop_end_bar_input)

        self.set_loop_btn = QPushButton("Set Loop")
        layout.addWidget(self.set_loop_btn)
