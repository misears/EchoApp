
# pyright: reportAttributeAccessIssue=false, reportArgumentType=false
"""Echo Pro — main application module.

Contains all UI classes and the application entry point.

Key classes
-----------
ClipFadeSettingsPopover   Floating dialog for per-clip fade/curve editing.
StemSourceDropZone        Drag-and-drop target for stem separation source files.
StemSeparationWorker      QObject worker that runs Demucs on a background QThread.
LufsHistoryWidget         Custom painter widget showing integrated LUFS over time.
EqCurvePreviewWidget      Custom painter widget for a 4-band EQ shape preview.
EchoProWindow             Base QMainWindow with all business logic (project I/O,
                          playback, recording, stems, voice, music generation).
TabbedEchoProWindow       Subclass that arranges the UI into a tab strip and is
                          the live application window launched at startup.

Launch path
-----------
main() at the bottom creates a QApplication, instantiates TabbedEchoProWindow,
and enters the Qt event loop.
"""

import os
import copy
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import soundfile as sf

def _configure_qt_font_fallback() -> None:
    """Point Qt at Windows system fonts when bundled Qt fonts are unavailable."""
    if os.name != "nt":
        return
    if os.environ.get("QT_QPA_FONTDIR"):
        return
    windows_fonts = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
    if windows_fonts.exists():
        os.environ["QT_QPA_FONTDIR"] = str(windows_fonts)


_configure_qt_font_fallback()

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
    QStatusBar, QPushButton, QFileDialog, QHBoxLayout, QLineEdit,
    QAbstractSpinBox,
    QComboBox, QProgressBar, QProgressDialog,
    QMessageBox, QDialog, QTextEdit, QListWidget, QListWidgetItem, QInputDialog,
    QPlainTextEdit,
    QTabWidget, QScrollArea, QGroupBox, QGridLayout, QFormLayout, QDialogButtonBox,
    QFrame, QSizePolicy, QSplitter, QMenu, QSpinBox, QCheckBox, QDial, QCompleter,
    QTableWidgetItem,
    QDoubleSpinBox, QSlider
)
from PySide6.QtCore import Qt, QTimer, QObject, QThread, Signal, Slot
from PySide6.QtGui import QPainter, QColor, QPen, QCursor, QDragEnterEvent, QDropEvent, QKeySequence, QShortcut

from project_model import Clip, Project, Track, TrackPlaybackSettings, new_empty_project, save_project, load_project
from audio_info import get_audio_length_ms
from timeline_widget import TimelineWidget
from playback_mixer import TARGET_SAMPLE_RATE, is_playback_active, mix_project_to_segment, play_project, project_duration_ms, stop_playback
from stems_engine import (
    DEFAULT_DEMUCS_MODEL,
    DEMUCS_MODEL_OPTIONS,
    StemCancelledError,
    StemDependencyError,
    StemSeparationError,
    add_stems_to_project,
    get_stem_backend_capability,
    resolve_stem_runtime,
    separate_stems,
)

from app_paths import ACE_MODELS_DIR, ECHO_ROOT, MODELS_DIR, PROJECTS_DIR, VOICES_DIR, ensure_dirs
from first_run import is_first_run, mark_first_run_done

from voice_store import load_voice_profiles, add_voice_profile
from voice_recorder import record_voice_to_wav
from voice_interface import VoiceProfileConfig
from voice_effects import apply_voice_conversion, get_voice_backend_capability

from music_generator import generate_music_clip, get_music_backend_capability
from song_planner import generate_song_sections
from recording_controller import RecordingController
from recording_ui_components import (
    RecordingDiagnosticsWidget,
    TakeListWidget,
    TrackMeterWidget,
    TransportBar,
    TransportPunchLoopWidget,
)
from audio_device import device_manager
from tools.dev.p5b_regression_runner import format_regression_summary as format_p5b_regression_summary, run_phase5b_regression_checks
from recording_recovery import RecoverySnapshotManager
from input_validation import parse_float, parse_int, parse_time_signature, run_common_validation_checks

from app.styles import DARK_STYLE
from app.ui.dialogs.first_run_dialog import FirstRunDialog
from app.ui.dialogs.new_project_dialog import NewProjectDialog
from app.ui.dialogs.project_browser_dialog import ProjectBrowserDialog
from app.ui.dialogs.track_playback_settings_dialog import TrackPlaybackSettingsDialog
from app.ui.dialogs.voice_manager_dialog import VoiceManagerDialog
from app.ui.tabbed_window_layout import (
    build_ace_step_tab,
    build_demucs_tab,
    build_help_tab,
    build_midi_mapping_tab,
    build_mastering_chain_tab,
    build_overview_tab,
    build_recording_tab,
    build_settings_tab,
    build_tools_tab,
    build_ui,
    build_voice_tab,
    on_timeline_add_clip_at,
    populate_voice_profile_combo,
    wrap_scroll,
)
from app.ui.widgets.collapsible_panel import CollapsiblePanel
from app.ui.widgets.track_mixer_row import TrackMixerRow
from app.controllers import TimelineSyncController
from app.controllers.status_telemetry_controller import StatusTelemetryController
from app.controllers.stem_workflow_controller import StemWorkflowController

# Symbolic stereo waveform placeholder shown in the Master Output section.
_MASTER_WAVEFORM_PLACEHOLDER = (
    "\u25ac\u25ac\u2580\u2584\u2580\u2588\u2580\u2584\u2580\u25ac  MASTER L  \u25ac\u25ac\u25ac  "
    "MASTER R  \u25ac\u2580\u2584\u2580\u2588\u2580\u2584\u2580\u25ac\u25ac"
)


class ClipFadeSettingsPopover(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._on_change = None
        self._on_close = None
        self._suspend_events = False
        self._clip_id: Optional[int] = None

        self.setWindowTitle("Fade Settings")
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)
        hint = QLabel("Adjust clip fades inline. Changes apply live while editing.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#aab4be;")
        layout.addWidget(hint)

        form = QFormLayout()
        self.fade_in_ms = QSpinBox()
        self.fade_in_ms.setRange(0, 600000)
        self.fade_in_ms.setSuffix(" ms")
        form.addRow("Fade In", self.fade_in_ms)

        self.fade_in_curve = QComboBox()
        self.fade_in_curve.addItems(["Linear", "Exp", "Log", "S-curve"])
        form.addRow("Fade In Curve", self.fade_in_curve)

        self.fade_out_ms = QSpinBox()
        self.fade_out_ms.setRange(0, 600000)
        self.fade_out_ms.setSuffix(" ms")
        form.addRow("Fade Out", self.fade_out_ms)

        self.fade_out_curve = QComboBox()
        self.fade_out_curve.addItems(["Linear", "Exp", "Log", "S-curve"])
        form.addRow("Fade Out Curve", self.fade_out_curve)
        layout.addLayout(form)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.hide)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.fade_in_ms.valueChanged.connect(self._emit_change)
        self.fade_out_ms.valueChanged.connect(self._emit_change)
        self.fade_in_curve.currentTextChanged.connect(self._emit_change)
        self.fade_out_curve.currentTextChanged.connect(self._emit_change)

    def bind(self, on_change, on_close=None) -> None:
        self._on_change = on_change
        self._on_close = on_close

    def set_clip_context(self, clip_id: int, *, fade_in_ms: int, fade_out_ms: int, fade_in_curve: str, fade_out_curve: str) -> None:
        self._clip_id = int(clip_id)
        self._suspend_events = True
        try:
            self.fade_in_ms.setValue(max(0, int(fade_in_ms)))
            self.fade_out_ms.setValue(max(0, int(fade_out_ms)))
            in_index = self.fade_in_curve.findText(str(fade_in_curve or "Linear"))
            out_index = self.fade_out_curve.findText(str(fade_out_curve or "Linear"))
            self.fade_in_curve.setCurrentIndex(in_index if in_index >= 0 else 0)
            self.fade_out_curve.setCurrentIndex(out_index if out_index >= 0 else 0)
        finally:
            self._suspend_events = False

    def clip_id(self) -> Optional[int]:
        return self._clip_id

    def _emit_change(self, *_args) -> None:
        if self._suspend_events or self._on_change is None or self._clip_id is None:
            return
        self._on_change(
            int(self._clip_id),
            int(self.fade_in_ms.value()),
            int(self.fade_out_ms.value()),
            str(self.fade_in_curve.currentText()),
            str(self.fade_out_curve.currentText()),
        )

    def hideEvent(self, event) -> None:
        if self._on_close is not None and self._clip_id is not None:
            self._on_close(int(self._clip_id))
        return super().hideEvent(event)


class StemSourceDropZone(QFrame):
    def __init__(self, on_path_dropped, parent=None):
        super().__init__(parent)
        self._on_path_dropped = on_path_dropped
        self._path_text = ""
        self.setAcceptDrops(True)
        self.setMinimumHeight(124)
        self.setObjectName("StemDropZone")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        self.title_label = QLabel("Drop source audio here")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size:13px; font-weight:600; color:#d6e6f2;")
        layout.addWidget(self.title_label)

        self.path_label = QLabel("No file selected")
        self.path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color:#89a3b8; font-size:11px;")
        layout.addWidget(self.path_label)

        self.setStyleSheet(
            "QFrame#StemDropZone { border: 1px dashed #2b4f6f; border-radius: 8px; background: #0f1e2d; }"
            "QFrame#StemDropZone[dragActive='true'] { border: 1px solid #00f0ff; background: #123149; }"
        )

    def set_current_path(self, path: Optional[Path]) -> None:
        if path is None:
            self._path_text = ""
            self.path_label.setText("No file selected")
            return
        self._path_text = str(path)
        self.path_label.setText(path.name)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            self.setProperty("dragActive", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()
            return
        event.ignore()


class StemSeparationWorker(QObject):
    progress = Signal(str)
    completed = Signal(dict)
    failed = Signal(str, str)
    cancelled = Signal(str)

    def __init__(self, *, source_path: Path, output_dir: Path, model_name: str):
        super().__init__()
        self._source_path = Path(source_path)
        self._output_dir = Path(output_dir)
        self._model_name = str(model_name)
        self._cancel_requested = False

    @Slot()
    def run(self) -> None:
        try:
            runtime = resolve_stem_runtime()
            stems = separate_stems(
                str(self._source_path),
                self._output_dir,
                demucs_executable=runtime.demucs_executable,
                demucs_repo=runtime.demucs_repo,
                ffmpeg_executable=runtime.ffmpeg_executable,
                demucs_model=self._model_name,
                progress_callback=self.progress.emit,
                cancel_check=lambda: bool(self._cancel_requested),
            )
            self.completed.emit(
                {
                    "stems": stems,
                    "output_dir": str(self._output_dir),
                    "model_name": self._model_name,
                    "source_name": self._source_path.name,
                }
            )
        except StemCancelledError as exc:
            self.cancelled.emit(str(exc))
        except StemDependencyError as exc:
            self.failed.emit("dependency", str(exc))
        except StemSeparationError as exc:
            self.failed.emit("separation", str(exc))
        except Exception as exc:
            self.failed.emit("unexpected", str(exc))

    @Slot()
    def request_cancel(self) -> None:
        self._cancel_requested = True

    def dragLeaveEvent(self, event) -> None:
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        return super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return
        for url in urls:
            local_path = url.toLocalFile()
            if not local_path:
                continue
            file_path = Path(local_path)
            if file_path.suffix.lower() in {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aiff"}:
                self._on_path_dropped(file_path)
                event.acceptProposedAction()
                return
        event.ignore()


class MidiInputWorker(QObject):
    cc_message = Signal(dict)
    status = Signal(str)
    devices = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self._running = False
        self._selected_device_name: Optional[str] = None
        self._selected_channel: int = -1

    @Slot()
    def run(self) -> None:
        self._running = True
        self._emit_devices()
        self.status.emit("MIDI worker started")

        mido_module = None
        try:
            import mido  # type: ignore

            mido_module = mido
        except Exception:
            self.status.emit("Python package 'mido' is not available; MIDI input monitoring disabled.")

        active_input = None
        active_input_name: Optional[str] = None

        while self._running:
            if mido_module is None:
                QThread.msleep(200)
                continue

            try:
                target_name = self._selected_device_name
                if target_name and target_name != active_input_name:
                    if active_input is not None:
                        active_input.close()
                        active_input = None
                    active_input = mido_module.open_input(target_name)
                    active_input_name = target_name
                    self.status.emit(f"Listening on MIDI input: {target_name}")

                if active_input is not None:
                    for message in active_input.iter_pending():
                        if str(getattr(message, "type", "")) != "control_change":
                            continue
                        channel = int(getattr(message, "channel", -1))
                        control = int(getattr(message, "control", -1))
                        value_raw = int(getattr(message, "value", 0))
                        if self._selected_channel >= 0 and channel != self._selected_channel:
                            continue
                        normalized = max(0.0, min(1.0, float(value_raw) / 127.0))
                        self.cc_message.emit(
                            {
                                "kind": "cc",
                                "channel": channel,
                                "cc": control,
                                "value_raw": value_raw,
                                "value_norm": normalized,
                                "device": active_input_name or "",
                            }
                        )
                QThread.msleep(2)
            except Exception as exc:
                self.status.emit(f"MIDI polling warning: {exc}")
                self._emit_devices()
                QThread.msleep(120)

        if active_input is not None:
            try:
                active_input.close()
            except Exception:
                pass
        self.status.emit("MIDI worker stopped")

    @Slot()
    def stop(self) -> None:
        self._running = False

    @Slot()
    def refresh_devices(self) -> None:
        self._emit_devices()

    @Slot(str)
    def set_selected_device(self, device_name: str) -> None:
        self._selected_device_name = str(device_name).strip() or None

    @Slot(int)
    def set_channel_filter(self, channel: int) -> None:
        self._selected_channel = int(channel)

    def _emit_devices(self) -> None:
        names: list[str] = []
        try:
            import mido  # type: ignore

            names = [str(name) for name in mido.get_input_names()]
        except Exception:
            names = []
        self.devices.emit(names)


class LufsHistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[float] = []
        self._target_db = -14.0
        self._current_db = -70.0
        self.setMinimumHeight(190)

    def set_values(self, history: list[float], target_db: float, current_db: float) -> None:
        self._history = [float(value) for value in history][-180:]
        self._target_db = float(target_db)
        self._current_db = float(current_db)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#09111c"))

        plot_rect = self.rect().adjusted(12, 14, -12, -16)
        painter.setPen(QPen(QColor("#23405a"), 1))
        painter.drawRect(plot_rect)

        min_db = -70.0
        max_db = 3.0

        def to_y(value: float) -> float:
            normalized = max(0.0, min(1.0, (float(value) - min_db) / max(1e-9, max_db - min_db)))
            return float(plot_rect.bottom()) - (normalized * float(plot_rect.height()))

        grid_pen = QPen(QColor("#173047"), 1)
        painter.setPen(grid_pen)
        for tick_db in (-60, -40, -20, 0):
            y = int(round(to_y(float(tick_db))))
            painter.drawLine(plot_rect.left(), y, plot_rect.right(), y)
            painter.drawText(4, y + 4, f"{tick_db}")

        target_y = int(round(to_y(self._target_db)))
        target_pen = QPen(QColor("#f2b84b"), 1, Qt.PenStyle.DashLine)
        painter.setPen(target_pen)
        painter.drawLine(plot_rect.left(), target_y, plot_rect.right(), target_y)

        if self._history:
            history = self._history[-180:]
            points = []
            step_x = float(plot_rect.width()) / max(1, len(history) - 1)
            for index, value in enumerate(history):
                x = float(plot_rect.left()) + (step_x * float(index))
                points.append((x, to_y(value)))

            line_pen = QPen(QColor("#00F0FF"), 2)
            painter.setPen(line_pen)
            for start, end in zip(points, points[1:]):
                painter.drawLine(int(round(start[0])), int(round(start[1])), int(round(end[0])), int(round(end[1])))

            current_x, current_y = points[-1]
            current_pen = QPen(QColor("#7fe0b5"), 1)
            painter.setPen(current_pen)
            painter.setBrush(QColor("#7fe0b5"))
            painter.drawEllipse(int(round(current_x)) - 3, int(round(current_y)) - 3, 6, 6)

        painter.setPen(QColor("#a8b7c6"))
        painter.drawText(plot_rect.left() + 8, plot_rect.top() + 16, f"Target {self._target_db:+.1f} LUFS-I")
        painter.drawText(plot_rect.left() + 8, plot_rect.bottom() - 6, f"Current {self._current_db:+.1f} LUFS-I")


class EqCurvePreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._bands = [0.0, 0.0, 0.0, 0.0]
        self.setMinimumHeight(110)

    def set_bands(self, bands: list[float]) -> None:
        self._bands = [float(value) for value in bands][:4]
        while len(self._bands) < 4:
            self._bands.append(0.0)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#0d1725"))

        plot_rect = self.rect().adjusted(10, 12, -10, -12)
        painter.setPen(QPen(QColor("#23405a"), 1))
        painter.drawRect(plot_rect)

        mid_y = int(round(plot_rect.center().y()))
        painter.setPen(QPen(QColor("#173047"), 1))
        painter.drawLine(plot_rect.left(), mid_y, plot_rect.right(), mid_y)

        def to_y(value: float) -> float:
            normalized = max(-12.0, min(12.0, float(value))) / 12.0
            return float(mid_y) - (normalized * (plot_rect.height() * 0.35))

        x_positions = [
            plot_rect.left() + int(plot_rect.width() * 0.12),
            plot_rect.left() + int(plot_rect.width() * 0.36),
            plot_rect.left() + int(plot_rect.width() * 0.64),
            plot_rect.left() + int(plot_rect.width() * 0.88),
        ]
        points = [(x_positions[index], to_y(value)) for index, value in enumerate(self._bands)]

        curve_pen = QPen(QColor("#00F0FF"), 2)
        painter.setPen(curve_pen)
        for start, end in zip(points, points[1:]):
            painter.drawLine(int(round(start[0])), int(round(start[1])), int(round(end[0])), int(round(end[1])))

        painter.setBrush(QColor("#f2b84b"))
        painter.setPen(QPen(QColor("#f2b84b"), 1))
        for point in points:
            painter.drawEllipse(int(round(point[0])) - 3, int(round(point[1])) - 3, 6, 6)

        painter.setPen(QColor("#a8b7c6"))
        painter.drawText(plot_rect.left() + 8, plot_rect.top() + 16, "EQ Curve")


class EchoProWindow(QMainWindow):
    def _initialize_shared_window_state(self) -> None:
        self.current_project: Project = new_empty_project("Untitled")
        self.next_clip_id = 1
        self.recording_controller = RecordingController("default_session", self.current_project.name)
        self.recording_controller.restore_session_preferences()
        self.recovery_manager = RecoverySnapshotManager()
        self.recording_meters = {}
        self.selected_track_index = None
        self.selected_input_device_id = None
        self.selected_output_device_id = None
        self.last_song_generation = None
        self.project_playhead_ms = 0
        self._project_playback_started_at: Optional[float] = None
        self._project_playback_start_ms = 0
        self._project_playback_end_ms = 0
        self._project_playback_manual_stop = False
        self._project_playback_segment: Optional[np.ndarray] = None
        self._project_playback_lufs_integrated_db = -70.0
        self._master_lufs_history: list[float] = []
        self._master_lufs_target_preset = "Spotify -14"
        self._master_lufs_target_db = -14.0
        self._master_short_term_lufs_db = -70.0
        self._master_momentary_lufs_db = -70.0
        self._master_true_peak_db = -80.0
        self._master_lufs_range_db = 0.0
        self.stem_source_path: Optional[Path] = None
        self.stem_output_dir: Optional[Path] = None
        self._stem_activity_lines: list[str] = []
        self._timeline_controller_bridge_connected = False
        self._syncing_timeline_scroll = False
        self._project_history_limit = 100
        self._project_undo_stack: list[dict] = []
        self._project_redo_stack: list[dict] = []
        self._project_history_suspended = False
        self._saved_project_fingerprint: Optional[str] = None
        self._timeline_zoom_step_ratio = 1.25
        self._automation_parameter_by_track: Dict[int, str] = {}
        self._clip_fade_popover: Optional[ClipFadeSettingsPopover] = None
        self._clip_fade_edit_state: Optional[dict] = None
        self._single_track_editor_tab: Optional[QWidget] = None
        self._single_track_editor_track_index: Optional[int] = None
        self._project_save_directory: Optional[Path] = None
        self._stem_worker_thread: Optional[QThread] = None
        self._stem_worker: Optional[StemSeparationWorker] = None
        self._stem_is_processing = False
        self._stem_pulse_state = False
        self._stem_started_at: Optional[float] = None
        self._stem_last_percent: int = 0
        self._stem_progress_filter = "all"
        self._latest_stem_results: dict[str, str] = {}
        self._latest_stem_output_dir: Optional[Path] = None
        self._stem_preview_volume_by_name: dict[str, float] = {}
        self._stem_preview_playing_name: Optional[str] = None
        self._ace_step_results: list[dict] = []
        self._ace_step_playing_path: Optional[str] = None
        self._ace_step_is_processing = False
        self._ace_step_pulse_state = False
        self._status_telemetry_controller: Optional[StatusTelemetryController] = None
        self._stem_workflow_controller: Optional[StemWorkflowController] = None
        self._settings_state: Optional[dict] = None
        self._settings_shortcut_table_syncing = False
        self._midi_worker_thread: Optional[QThread] = None
        self._midi_worker: Optional[MidiInputWorker] = None
        self._midi_input_devices: list[str] = []
        self._midi_mapping_rows: list[dict] = []
        self._midi_learn_active = False
        self._midi_learn_pending_row: Optional[int] = None
        self._global_shortcuts: list[QShortcut] = []

    def _shutdown_stem_worker(self) -> None:
        thread = self._stem_worker_thread
        worker = self._stem_worker
        if thread is None:
            return

        if thread.isRunning() and worker is not None:
            worker.request_cancel()
            deadline = time.monotonic() + 6.0
            while thread.isRunning() and time.monotonic() < deadline:
                thread.wait(120)
                QApplication.processEvents()

        if thread.isRunning():
            thread.quit()
            thread.wait(1000)

        if thread.isRunning():
            thread.terminate()
            thread.wait(1000)

        self._stem_worker = None
        self._stem_worker_thread = None
        self._stem_is_processing = False

    def _shutdown_midi_worker(self) -> None:
        worker = self._midi_worker
        thread = self._midi_worker_thread
        if worker is not None:
            worker.stop()
        if thread is not None:
            thread.quit()
            thread.wait(2000)
            thread.deleteLater()
        self._midi_worker = None
        self._midi_worker_thread = None

    def closeEvent(self, event) -> None:
        self._shutdown_stem_worker()
        self._shutdown_midi_worker()
        return super().closeEvent(event)

    def _get_status_telemetry_controller(self) -> StatusTelemetryController:
        if self._status_telemetry_controller is None:
            self._status_telemetry_controller = StatusTelemetryController(self)
        return self._status_telemetry_controller

    def _get_stem_workflow_controller(self) -> StemWorkflowController:
        if self._stem_workflow_controller is None:
            self._stem_workflow_controller = StemWorkflowController(self)
        return self._stem_workflow_controller

    def _setup_status_bar_widgets(self) -> None:
        self._get_status_telemetry_controller().setup_status_bar_widgets()

    def _read_system_usage_percent(self) -> Tuple[Optional[float], Optional[float]]:
        return self._get_status_telemetry_controller().read_system_usage_percent()

    def _compute_project_fingerprint(self) -> str:
        payload = {
            "name": self.current_project.name,
            "tracks": [asdict(track) for track in self.current_project.tracks],
            "clips": [asdict(clip) for clip in self.current_project.clips],
            "metadata": self.current_project.metadata,
            "next_clip_id": int(self.next_clip_id),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def _mark_project_saved_state(self) -> None:
        self._saved_project_fingerprint = self._compute_project_fingerprint()
        self._refresh_status_bar_telemetry()

    def _is_project_dirty(self) -> bool:
        if self._saved_project_fingerprint is None:
            return True
        return self._compute_project_fingerprint() != self._saved_project_fingerprint

    def _refresh_status_bar_telemetry(self) -> None:
        self._get_status_telemetry_controller().refresh_status_bar_telemetry()
        self._refresh_application_state_machine()

    def _refresh_application_state_machine(self) -> None:
        has_project_content = bool(self.current_project.tracks or self.current_project.clips)
        project_name = str(self.current_project.name or "").strip() or "Untitled"
        is_dirty = self._is_project_dirty()
        is_recording = bool(
            self.recording_controller.status.is_recording
            or self.recording_controller.status.count_in_active
        )
        is_playing = self._is_project_playback_running()
        is_processing = bool(self._stem_is_processing or self._ace_step_is_processing)

        if not has_project_content and project_name.lower() == "untitled":
            base_state = "Idle"
        elif is_recording:
            base_state = "Recording"
        elif is_playing:
            base_state = "Playing"
        elif is_processing:
            base_state = "AI Processing"
        elif self._midi_learn_active:
            base_state = "MIDI Learn"
        else:
            base_state = "Project Open"

        badges: list[str] = []
        if self._midi_learn_active and base_state != "MIDI Learn":
            badges.append("MIDI Learn")
        if is_processing and base_state != "AI Processing":
            badges.append("AI")
        if is_dirty:
            badges.append("Unsaved")

        mode_label = f"State: {base_state}"
        if badges:
            mode_label = f"{mode_label} | {', '.join(badges)}"
        if hasattr(self, "status_mode_label"):
            self.status_mode_label.setText(mode_label)

        title = f"Echo Pro - {project_name}"
        if is_dirty:
            title = f"{title} *"
        if base_state != "Project Open":
            title = f"{title} [{base_state}]"
        if badges:
            title = f"{title} [{' | '.join(badges)}]"
        if self.windowTitle() != title:
            self.setWindowTitle(title)

    def _initialize_shared_window_timers(self, *, start_recording_timer: bool) -> None:
        self.recording_timer = QTimer(self)
        self.recording_timer.setInterval(100)
        self.recording_timer.timeout.connect(self.refresh_recording_meters)
        if start_recording_timer:
            self.recording_timer.start()

        self.project_playback_timer = QTimer(self)
        self.project_playback_timer.setInterval(75)
        self.project_playback_timer.timeout.connect(self._poll_project_playback)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Echo Pro")

        self._initialize_shared_window_state()

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self._setup_status_bar_widgets()

        self._initialize_shared_window_timers(start_recording_timer=True)

        layout = QVBoxLayout()

        # Top bar
        top_layout = QHBoxLayout()
        top_layout.setSpacing(6)
        self.project_name_label = QLabel("Project: Untitled")
        top_layout.addWidget(self.project_name_label)

        for symbol, slot, tip in [
            ("+", self.new_project, "Create new project"),
            ("\U0001f4c2", self.open_project, "Open project"),
            ("\U0001f4be", self.save_project_dialog, "Save project"),
            ("\U0001f50d", self.browse_projects, "Browse projects"),
        ]:
            button = QPushButton(symbol)
            self._configure_symbol_button(button, symbol, tip, width=34)
            button.clicked.connect(slot)
            top_layout.addWidget(button)

        layout.addLayout(top_layout)

        # Track controls
        track_controls_layout = QVBoxLayout()

        track_add_row = QHBoxLayout()
        self.track_name_input = QLineEdit()
        self.track_name_input.setPlaceholderText("Track name")
        track_add_row.addWidget(self.track_name_input)

        add_track_btn = QPushButton("Add Track")
        add_track_btn.clicked.connect(self.add_track)
        track_add_row.addWidget(add_track_btn)

        rename_track_btn = QPushButton("Rename Selected")
        rename_track_btn.clicked.connect(self.rename_selected_track)
        track_add_row.addWidget(rename_track_btn)

        delete_track_btn = QPushButton("Delete Selected")
        delete_track_btn.clicked.connect(self.delete_selected_track)
        track_add_row.addWidget(delete_track_btn)

        track_controls_layout.addLayout(track_add_row)

        self.track_list = QListWidget()
        self.track_list.currentRowChanged.connect(self.on_track_selection_changed)
        track_controls_layout.addWidget(self.track_list)

        track_action_row = QHBoxLayout()

        move_up_btn = QPushButton("Move Up")
        move_up_btn.clicked.connect(lambda: self.move_selected_track(-1))
        track_action_row.addWidget(move_up_btn)

        move_down_btn = QPushButton("Move Down")
        move_down_btn.clicked.connect(lambda: self.move_selected_track(1))
        track_action_row.addWidget(move_down_btn)

        mute_btn = QPushButton("Toggle Mute")
        mute_btn.clicked.connect(self.toggle_selected_track_mute)
        track_action_row.addWidget(mute_btn)

        solo_btn = QPushButton("Toggle Solo")
        solo_btn.clicked.connect(self.toggle_selected_track_solo)
        track_action_row.addWidget(solo_btn)

        arm_selected_btn = QPushButton("Arm/Disarm Selected")
        arm_selected_btn.clicked.connect(self.toggle_arm_selected_track)
        track_action_row.addWidget(arm_selected_btn)

        track_controls_layout.addLayout(track_action_row)
        layout.addLayout(track_controls_layout)

        # Stems controls
        stems_layout = QHBoxLayout()
        stems_btn = QPushButton("Split song into stems")
        stems_btn.clicked.connect(self.split_song_into_stems)
        stems_layout.addWidget(stems_btn)
        layout.addLayout(stems_layout)

        # Clip controls
        clip_layout = QHBoxLayout()
        self.clip_track_index_input = QLineEdit()
        self.clip_track_index_input.setPlaceholderText("Track index (0,1,2...)")
        clip_layout.addWidget(self.clip_track_index_input)

        self.clip_start_sec_input = QLineEdit()
        self.clip_start_sec_input.setPlaceholderText("Start time (seconds)")
        clip_layout.addWidget(self.clip_start_sec_input)

        add_clip_btn = QPushButton("Add Clip from File")
        add_clip_btn.clicked.connect(self.add_clip_from_file)
        clip_layout.addWidget(add_clip_btn)

        layout.addLayout(clip_layout)

        # Volume / playback controls
        vol_layout = QHBoxLayout()
        self.volume_track_index_input = QLineEdit()
        self.volume_track_index_input.setPlaceholderText("Track index for volume")
        vol_layout.addWidget(self.volume_track_index_input)

        self.volume_db_input = QLineEdit()
        self.volume_db_input.setPlaceholderText("Volume dB (e.g., -5, 0, +3)")
        vol_layout.addWidget(self.volume_db_input)

        set_vol_btn = QPushButton("Set Track Volume")
        set_vol_btn.clicked.connect(self.set_track_volume)
        vol_layout.addWidget(set_vol_btn)

        self.play_project_btn = QPushButton("Play")
        self.play_project_btn.clicked.connect(self.play_current_project)
        vol_layout.addWidget(self.play_project_btn)

        self.stop_project_btn = QPushButton("Stop")
        self.stop_project_btn.clicked.connect(self.stop_current_project_playback)
        self.stop_project_btn.setEnabled(False)
        self._configure_symbol_button(self.play_project_btn, "\u25b6", "Play project")
        self._configure_symbol_button(self.stop_project_btn, "\u25a0", "Stop playback")
        vol_layout.addWidget(self.stop_project_btn)

        self.jump_to_transport_start_btn = QPushButton("Jump to Start")
        self.jump_to_transport_start_btn.clicked.connect(self.jump_to_transport_start)
        self._configure_symbol_button(self.jump_to_transport_start_btn, "\u23ee", "Jump to start")
        vol_layout.addWidget(self.jump_to_transport_start_btn)

        self.jump_to_transport_end_btn = QPushButton("Jump to End")
        self.jump_to_transport_end_btn.clicked.connect(self.jump_to_transport_end)
        self._configure_symbol_button(self.jump_to_transport_end_btn, "\u23ed", "Jump to end")
        vol_layout.addWidget(self.jump_to_transport_end_btn)

        self.playback_position_label = QLabel("Playhead 0.00s")
        vol_layout.addWidget(self.playback_position_label)

        layout.addLayout(vol_layout)

        # Recording controls
        recording_layout = QVBoxLayout()

        device_row = QHBoxLayout()
        self.input_device_combo = QComboBox()
        self.output_device_combo = QComboBox()
        refresh_devices_btn = QPushButton("Refresh Devices")
        refresh_devices_btn.clicked.connect(self.refresh_audio_device_selectors)
        test_devices_btn = QPushButton("Test Devices")
        test_devices_btn.clicked.connect(self.test_audio_devices)
        self._configure_symbol_button(refresh_devices_btn, "\u21bb", "Refresh audio devices")
        self._configure_symbol_button(test_devices_btn, "\U0001f50a", "Test audio devices")
        device_row.addWidget(QLabel("Input"))
        device_row.addWidget(self.input_device_combo)
        device_row.addWidget(QLabel("Output"))
        device_row.addWidget(self.output_device_combo)
        device_row.addWidget(refresh_devices_btn)
        device_row.addWidget(test_devices_btn)
        recording_layout.addLayout(device_row)

        transport_row = QHBoxLayout()
        self.transport_bar = TransportBar()
        self.transport_bar.record_button.clicked.connect(self.start_recording_session)
        self.transport_bar.stop_button.clicked.connect(self.stop_recording_session)
        self.transport_bar.undo_button.clicked.connect(self.undo_last_recording_take)
        self.transport_bar.redo_button.clicked.connect(self.redo_last_recording_take)
        self.transport_bar.click_button.clicked.connect(self.toggle_metronome)
        self.transport_bar.stop_button.setEnabled(False)
        transport_row.addWidget(self.transport_bar)

        self.record_track_input = QLineEdit()
        self.record_track_input.setPlaceholderText("Arm track index")
        transport_row.addWidget(self.record_track_input)

        arm_btn = QPushButton("Arm Track")
        arm_btn.clicked.connect(self.arm_recording_track)
        transport_row.addWidget(arm_btn)

        arm_all_btn = QPushButton("Arm All")
        arm_all_btn.clicked.connect(self.arm_all_recording_tracks)
        transport_row.addWidget(arm_all_btn)

        clear_armed_btn = QPushButton("Clear Armed")
        clear_armed_btn.clicked.connect(self.clear_armed_recording_tracks)
        transport_row.addWidget(clear_armed_btn)

        self.record_tempo_input = QLineEdit()
        self.record_tempo_input.setPlaceholderText("Tempo BPM")
        transport_row.addWidget(self.record_tempo_input)

        set_tempo_btn = QPushButton("Set Tempo")
        set_tempo_btn.clicked.connect(self.set_recording_tempo)
        transport_row.addWidget(set_tempo_btn)

        recording_layout.addLayout(transport_row)

        timing_row = QHBoxLayout()
        self.record_time_sig_input = QLineEdit()
        self.record_time_sig_input.setPlaceholderText("Time Sig (e.g., 4/4)")
        timing_row.addWidget(self.record_time_sig_input)

        set_time_sig_btn = QPushButton("Set Time Sig")
        set_time_sig_btn.clicked.connect(self.set_recording_time_signature)
        timing_row.addWidget(set_time_sig_btn)

        self.record_count_in_input = QLineEdit()
        self.record_count_in_input.setPlaceholderText("Count-In Bars")
        timing_row.addWidget(self.record_count_in_input)

        set_count_in_btn = QPushButton("Set Count-In")
        set_count_in_btn.clicked.connect(self.set_recording_count_in)
        timing_row.addWidget(set_count_in_btn)

        recording_layout.addLayout(timing_row)

        self.punch_loop_widget = TransportPunchLoopWidget()
        self.pre_roll_bar_input = self.punch_loop_widget.pre_roll_bar_input
        self.post_roll_bar_input = self.punch_loop_widget.post_roll_bar_input
        self.punch_mode_combo = self.punch_loop_widget.punch_mode_combo
        self.punch_in_bar_input = self.punch_loop_widget.punch_in_bar_input
        self.punch_out_bar_input = self.punch_loop_widget.punch_out_bar_input
        self.loop_mode_combo = self.punch_loop_widget.loop_mode_combo
        self.loop_start_bar_input = self.punch_loop_widget.loop_start_bar_input
        self.loop_end_bar_input = self.punch_loop_widget.loop_end_bar_input

        self.punch_mode_combo.currentIndexChanged.connect(self.on_punch_mode_changed)
        self.loop_mode_combo.currentIndexChanged.connect(self.on_loop_mode_changed)
        self.punch_loop_widget.set_roll_btn.clicked.connect(self.set_recording_pre_post_roll)
        self.punch_loop_widget.set_punch_btn.clicked.connect(self.set_recording_punch_range)
        self.punch_loop_widget.set_loop_btn.clicked.connect(self.set_recording_loop_range)
        recording_layout.addWidget(self.punch_loop_widget)

        self.recording_status_label = QLabel("Recording: idle")
        recording_layout.addWidget(self.recording_status_label)

        self.recording_diagnostics_widget = RecordingDiagnosticsWidget()
        recording_layout.addWidget(self.recording_diagnostics_widget)

        take_review_header = QHBoxLayout()
        take_review_header.addWidget(QLabel("Take Review Track"))
        self.take_track_combo = QComboBox()
        self.take_track_combo.currentIndexChanged.connect(self.refresh_take_review_list)
        take_review_header.addWidget(self.take_track_combo)

        self.take_sort_combo = QComboBox()
        self.take_sort_combo.addItem("Newest First", "newest")
        self.take_sort_combo.addItem("Oldest First", "oldest")
        self.take_sort_combo.currentIndexChanged.connect(self.on_take_review_preferences_changed)
        take_review_header.addWidget(self.take_sort_combo)

        self.take_filter_combo = QComboBox()
        self.take_filter_combo.addItem("All Takes", "all")
        self.take_filter_combo.addItem("Clipped Only", "clipped")
        self.take_filter_combo.addItem("Active Only", "active")
        self.take_filter_combo.currentIndexChanged.connect(self.on_take_review_preferences_changed)
        take_review_header.addWidget(self.take_filter_combo)

        self.take_view_mode_combo = QComboBox()
        self.take_view_mode_combo.addItem("Expanded", "expanded")
        self.take_view_mode_combo.addItem("Compact", "compact")
        self.take_view_mode_combo.currentIndexChanged.connect(self.on_take_review_preferences_changed)
        take_review_header.addWidget(self.take_view_mode_combo)

        refresh_takes_btn = QPushButton("Refresh Takes")
        refresh_takes_btn.clicked.connect(self.refresh_take_review_list)
        take_review_header.addWidget(refresh_takes_btn)
        recording_layout.addLayout(take_review_header)

        self.take_list_widget = TakeListWidget()
        self.take_review_list = self.take_list_widget.list_widget
        self.take_list_widget.on_item_double_clicked(self.audition_selected_take)
        recording_layout.addWidget(self.take_list_widget)

        badge_legend = QLabel(
            "<span style='color:#148250; font-weight:bold;'>■ ACTIVE</span> "
            "<span style='color:#cfcfcf;'>Selected take used in playback</span>    "
            "<span style='color:#6e6e6e; font-weight:bold;'>■ ALT</span> "
            "<span style='color:#cfcfcf;'>Inactive alternative take</span>"
        )
        badge_legend.setToolTip("Timeline badge legend for recording takes")
        recording_layout.addWidget(badge_legend)

        take_actions_row = QHBoxLayout()
        use_take_btn = QPushButton("Set Active Take")
        use_take_btn.clicked.connect(self.set_selected_take_active)
        take_actions_row.addWidget(use_take_btn)

        audition_take_btn = QPushButton("Audition Selected")
        audition_take_btn.clicked.connect(self.audition_selected_take)
        take_actions_row.addWidget(audition_take_btn)

        self.take_loop_combo = QComboBox()
        self.take_loop_combo.addItem("One-Shot", False)
        self.take_loop_combo.addItem("Loop", True)
        self.take_loop_combo.currentIndexChanged.connect(self.on_take_review_preferences_changed)
        take_actions_row.addWidget(self.take_loop_combo)

        self.hide_inactive_take_clips_btn = QPushButton("Hide Inactive Takes")
        self.hide_inactive_take_clips_btn.setCheckable(True)
        self.hide_inactive_take_clips_btn.toggled.connect(self.on_hide_inactive_take_clips_toggled)
        take_actions_row.addWidget(self.hide_inactive_take_clips_btn)

        stop_audition_btn = QPushButton("Stop Audition")
        stop_audition_btn.clicked.connect(self.stop_take_audition)
        take_actions_row.addWidget(stop_audition_btn)

        audition_active_btn = QPushButton("Audition Active")
        audition_active_btn.clicked.connect(self.audition_active_take)
        take_actions_row.addWidget(audition_active_btn)

        delete_take_btn = QPushButton("Delete Selected Take")
        delete_take_btn.clicked.connect(self.delete_selected_take)
        take_actions_row.addWidget(delete_take_btn)

        keeper_btn = QPushButton("Toggle Keeper")
        keeper_btn.clicked.connect(self.toggle_selected_take_keeper)
        take_actions_row.addWidget(keeper_btn)

        mute_take_btn = QPushButton("Toggle Take Mute")
        mute_take_btn.clicked.connect(self.toggle_selected_take_muted)
        take_actions_row.addWidget(mute_take_btn)

        rate_down_btn = QPushButton("Rate -")
        rate_down_btn.clicked.connect(lambda: self.rate_selected_take(-1))
        take_actions_row.addWidget(rate_down_btn)

        rate_up_btn = QPushButton("Rate +")
        rate_up_btn.clicked.connect(lambda: self.rate_selected_take(1))
        take_actions_row.addWidget(rate_up_btn)

        best_take_btn = QPushButton("Use Best Take")
        best_take_btn.clicked.connect(self.use_best_take_for_selected_track)
        take_actions_row.addWidget(best_take_btn)

        note_clean_btn = QPushButton("Note: Clean")
        note_clean_btn.clicked.connect(lambda: self.apply_selected_take_note_template("clean"))
        take_actions_row.addWidget(note_clean_btn)

        note_noisy_btn = QPushButton("Note: Noisy")
        note_noisy_btn.clicked.connect(lambda: self.apply_selected_take_note_template("noisy"))
        take_actions_row.addWidget(note_noisy_btn)

        note_timing_btn = QPushButton("Note: Timing")
        note_timing_btn.clicked.connect(lambda: self.apply_selected_take_note_template("timing"))
        take_actions_row.addWidget(note_timing_btn)

        recording_layout.addLayout(take_actions_row)

        comp_actions_row = QHBoxLayout()
        comp_actions_row.addWidget(QLabel("Comp Range (sec)"))

        self.comp_start_sec_input = QLineEdit()
        self.comp_start_sec_input.setPlaceholderText("Start")
        comp_actions_row.addWidget(self.comp_start_sec_input)

        self.comp_end_sec_input = QLineEdit()
        self.comp_end_sec_input.setPlaceholderText("End")
        comp_actions_row.addWidget(self.comp_end_sec_input)

        create_comp_btn = QPushButton("Create Comp Region")
        create_comp_btn.clicked.connect(self.create_comp_region_from_selection)
        comp_actions_row.addWidget(create_comp_btn)

        assign_comp_btn = QPushButton("Assign Selected Take")
        assign_comp_btn.clicked.connect(self.assign_selected_take_to_comp_region)
        comp_actions_row.addWidget(assign_comp_btn)

        clear_comp_btn = QPushButton("Clear Comp Region")
        clear_comp_btn.clicked.connect(self.clear_comp_region_from_selection)
        comp_actions_row.addWidget(clear_comp_btn)

        recording_layout.addLayout(comp_actions_row)

        recovery_history_row = QHBoxLayout()
        recovery_history_row.addWidget(QLabel("Recovery History"))
        self.recovery_history_combo = QComboBox()
        recovery_history_row.addWidget(self.recovery_history_combo)

        refresh_recovery_btn = QPushButton("Refresh History")
        refresh_recovery_btn.clicked.connect(self.refresh_recovery_history)
        recovery_history_row.addWidget(refresh_recovery_btn)

        restore_recovery_btn = QPushButton("Restore Selected")
        restore_recovery_btn.clicked.connect(self.restore_selected_recovery_snapshot)
        recovery_history_row.addWidget(restore_recovery_btn)
        recording_layout.addLayout(recovery_history_row)

        self.meter_container = QVBoxLayout()
        self._build_recording_meters()
        recording_layout.addLayout(self.meter_container)

        layout.addLayout(recording_layout)

        # Voice effect controls
        voice_layout = QHBoxLayout()

        self.voice_track_index_input = QLineEdit()
        self.voice_track_index_input.setPlaceholderText("Track index (clip)")
        voice_layout.addWidget(self.voice_track_index_input)

        self.voice_clip_id_input = QLineEdit()
        self.voice_clip_id_input.setPlaceholderText("Clip ID")
        voice_layout.addWidget(self.voice_clip_id_input)

        self.voice_profile_name_input = QLineEdit()
        self.voice_profile_name_input.setPlaceholderText("Voice profile name")
        voice_layout.addWidget(self.voice_profile_name_input)

        apply_voice_btn = QPushButton("Apply Voice Effect")
        apply_voice_btn.clicked.connect(self.apply_voice_effect_to_clip)
        voice_layout.addWidget(apply_voice_btn)

        manage_voices_btn = QPushButton("Manage Voices")
        manage_voices_btn.clicked.connect(self.open_voice_manager)
        voice_layout.addWidget(manage_voices_btn)

        layout.addLayout(voice_layout)

        # Music Generator Panel
        gen_layout = QHBoxLayout()

        self.gen_style = QLineEdit()
        self.gen_style.setPlaceholderText("Style (e.g., lofi, rock)")
        gen_layout.addWidget(self.gen_style)

        self.gen_genre = QLineEdit()
        self.gen_genre.setPlaceholderText("Genre (e.g., EDM, orchestral)")
        gen_layout.addWidget(self.gen_genre)

        self.gen_mood = QLineEdit()
        self.gen_mood.setPlaceholderText("Mood (e.g., calm, energetic)")
        gen_layout.addWidget(self.gen_mood)

        self.gen_lyrics = QLineEdit()
        self.gen_lyrics.setPlaceholderText("Lyrics snippet")
        gen_layout.addWidget(self.gen_lyrics)

        self.gen_duration = QLineEdit()
        self.gen_duration.setPlaceholderText("Duration (sec, 10–30)")
        gen_layout.addWidget(self.gen_duration)

        gen_btn = QPushButton("Generate Clip")
        gen_btn.clicked.connect(self.generate_single_clip)
        gen_layout.addWidget(gen_btn)

        layout.addLayout(gen_layout)

        # Song Planner Panel
        planner_layout = QHBoxLayout()

        self.plan_total_length = QLineEdit()
        self.plan_total_length.setPlaceholderText("Total length (sec)")
        planner_layout.addWidget(self.plan_total_length)

        self.plan_structure = QLineEdit()
        self.plan_structure.setPlaceholderText("Structure (Intro,Verse,Chorus)")
        planner_layout.addWidget(self.plan_structure)

        self.plan_key = QLineEdit()
        self.plan_key.setPlaceholderText("Key (e.g., C major)")
        planner_layout.addWidget(self.plan_key)

        self.plan_chords = QLineEdit()
        self.plan_chords.setPlaceholderText("Chords (C-G-Am-F)")
        planner_layout.addWidget(self.plan_chords)

        self.plan_time_sig = QLineEdit()
        self.plan_time_sig.setPlaceholderText("Time signature (4/4)")
        planner_layout.addWidget(self.plan_time_sig)

        self.plan_tempo = QLineEdit()
        self.plan_tempo.setPlaceholderText("Tempo (BPM)")
        planner_layout.addWidget(self.plan_tempo)

        self.plan_lyrics = QTextEdit()
        self.plan_lyrics.setPlaceholderText("Full lyrics")
        planner_layout.addWidget(self.plan_lyrics)

        plan_btn = QPushButton("Generate Full Song (Clips)")
        plan_btn.clicked.connect(self.generate_full_song)
        planner_layout.addWidget(plan_btn)

        layout.addLayout(planner_layout)

        alter_layout = QHBoxLayout()
        self.alter_section_selector = QComboBox()
        self.alter_section_selector.currentIndexChanged.connect(self.on_alter_section_selector_changed)
        alter_layout.addWidget(self.alter_section_selector)

        self.alter_section_index_input = QLineEdit()
        self.alter_section_index_input.setPlaceholderText("Alter section index (0-based)")
        alter_layout.addWidget(self.alter_section_index_input)

        self.alter_section_lyrics_input = QLineEdit()
        self.alter_section_lyrics_input.setPlaceholderText("Optional override lyrics for this section")
        alter_layout.addWidget(self.alter_section_lyrics_input)

        alter_btn = QPushButton("Alter Section Without Full Regenerate")
        alter_btn.clicked.connect(self.alter_generated_song_section)
        alter_layout.addWidget(alter_btn)

        layout.addLayout(alter_layout)

        # Cloud Settings
        cloud_layout = QHBoxLayout()
        self.cloud_enabled = QLineEdit()
        self.cloud_enabled.setPlaceholderText("Cloud backend? yes/no (default: no = ACE Step 1.5 local)")
        self.cloud_enabled.setText("no")
        cloud_layout.addWidget(self.cloud_enabled)
        layout.addLayout(cloud_layout)

        # Timeline
        self.timeline = TimelineWidget(self.current_project)
        self.timeline.on_project_changed = self._on_timeline_project_changed
        self.timeline.on_comp_range_selected = self.on_timeline_comp_range_selected
        self.timeline.on_track_selected = self._on_timeline_track_selected
        self.timeline.on_track_double_click = self._on_timeline_track_double_click
        self.timeline.on_automation_points_changed = self._on_timeline_automation_points_changed
        self.timeline.on_clip_fade_changed = self._on_timeline_clip_fade_changed
        layout.addWidget(self.timeline)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.refresh_track_list()
        self.refresh_audio_device_selectors()
        self.sync_project_tracks_to_recording_engine()
        self.sync_recording_controls_from_controller()
        self._apply_take_review_preferences()
        self.refresh_take_track_selector()
        self.refresh_take_review_list()
        self.refresh_alter_section_selector()
        self.update_recording_status_label()
        self._prompt_recovery_for_current_session()
        self.refresh_recovery_history()

        self.update_status("Ready")

    def _configure_symbol_button(self, button: QPushButton, symbol: str, tooltip: str, *, width: int = 36, height: int = 28) -> None:
        button.setText(symbol)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setFixedSize(width, height)

    def _sync_metronome_button_state(self, running: bool) -> None:
        for bar in self._recording_transport_bars():
            if hasattr(bar, "set_metronome_enabled"):
                bar.set_metronome_enabled(running)
        mixer_layout = getattr(self, "main_mixer_view", None)
        if mixer_layout is not None and hasattr(mixer_layout, "_sync_mixer_transport_controls_from_window"):
            mixer_layout._sync_mixer_transport_controls_from_window()

    def _recording_transport_bars(self) -> list[TransportBar]:
        bars: list[TransportBar] = []
        for attr_name in ("transport_bar", "mixer_transport_bar"):
            bar = getattr(self, attr_name, None)
            if isinstance(bar, TransportBar) and bar not in bars:
                bars.append(bar)
        return bars

    def _set_recording_transport_button_state(self, *, can_record: bool, can_stop: bool) -> None:
        for bar in self._recording_transport_bars():
            bar.record_button.setEnabled(bool(can_record))
            bar.stop_button.setEnabled(bool(can_stop))

    def _on_timeline_project_changed(self):
        self.refresh_timeline()
        self.update_status("Timeline updated")

    def refresh_alter_section_selector(self):
        if not hasattr(self, "alter_section_selector"):
            return
        current_index = self.alter_section_selector.currentIndex()
        self.alter_section_selector.blockSignals(True)
        self.alter_section_selector.clear()
        if self.last_song_generation and isinstance(self.last_song_generation.get("sections"), list):
            for section in self.last_song_generation["sections"]:
                section_index = int(section.get("section_index", 0))
                section_name = str(section.get("section_name", f"Section {section_index}"))
                self.alter_section_selector.addItem(f"{section_index}: {section_name}", section_index)
        self.alter_section_selector.blockSignals(False)
        if self.alter_section_selector.count() > 0:
            safe_index = current_index if 0 <= current_index < self.alter_section_selector.count() else 0
            self.alter_section_selector.setCurrentIndex(safe_index)
            self.on_alter_section_selector_changed()

    def on_alter_section_selector_changed(self, *_args):
        if not hasattr(self, "alter_section_selector"):
            return
        value = self.alter_section_selector.currentData()
        if value is not None:
            self.alter_section_index_input.setText(str(value))

    def _classify_stem_log_level(self, message: str) -> str:
        return self._get_stem_workflow_controller().classify_stem_log_level(message)

    def _append_stem_activity(self, text: str, *, reset: bool = False, level: Optional[str] = None) -> None:
        self._get_stem_workflow_controller().append_stem_activity(text, reset=reset, level=level)

    def _refresh_stem_activity_log_view(self) -> None:
        self._get_stem_workflow_controller().refresh_stem_activity_log_view()

    def _on_stem_log_filter_changed(self, *_args) -> None:
        self._get_stem_workflow_controller().on_stem_log_filter_changed(*_args)

    def _copy_stem_log(self) -> None:
        self._get_stem_workflow_controller().copy_stem_log()

    def _save_stem_log(self) -> None:
        self._get_stem_workflow_controller().save_stem_log()

    def _clear_stem_log(self) -> None:
        self._get_stem_workflow_controller().clear_stem_log()

    def _set_stem_progress_state_label(self, text: str) -> None:
        self._get_stem_workflow_controller().set_stem_progress_state_label(text)

    def _reset_stem_progress_ui(self, *, state_text: str = "Idle") -> None:
        self._get_stem_workflow_controller().reset_stem_progress_ui(state_text=state_text)

    def _update_stem_elapsed_eta(self, percent: int) -> None:
        self._get_stem_workflow_controller().update_stem_elapsed_eta(percent)

    def _update_stem_progress_from_message(self, message: str) -> None:
        self._get_stem_workflow_controller().update_stem_progress_from_message(message)

    def _set_stem_status(self, summary: str, *, detail: Optional[str] = None, reset_activity: bool = False) -> None:
        self._get_stem_workflow_controller().set_stem_status(summary, detail=detail, reset_activity=reset_activity)

    def _format_file_size(self, path: Path) -> str:
        return self._get_stem_workflow_controller().format_file_size(path)

    def _project_folder_for_transfer(self) -> Path:
        return self._get_stem_workflow_controller().project_folder_for_transfer()

    def _render_waveform_ascii_for_file(self, file_path: Path, columns: int = 32) -> str:
        return self._get_stem_workflow_controller().render_waveform_ascii_for_file(file_path, columns=columns)

    def _refresh_stem_preview_rows(self) -> None:
        self._get_stem_workflow_controller().refresh_stem_preview_rows()

    def _set_stem_preview_volume(self, stem_name: str, dial_value: int) -> None:
        self._get_stem_workflow_controller().set_stem_preview_volume(stem_name, dial_value)

    def _toggle_stem_preview_playback(self, stem_name: str) -> None:
        self._get_stem_workflow_controller().toggle_stem_preview_playback(stem_name)

    def _play_stem_preview(self, stem_name: str) -> None:
        self._get_stem_workflow_controller().play_stem_preview(stem_name)

    def _stop_stem_preview_playback(self) -> None:
        self._get_stem_workflow_controller().stop_stem_preview_playback()

    def _refresh_ace_step_results(self) -> None:
        if not hasattr(self, "ace_results_list"):
            return
        results = getattr(self, "_ace_step_results", [])
        self.ace_results_list.clear()
        if not results:
            self.ace_results_list.addItem("Generated results will appear here.")
            return

        for index, result in enumerate(results):
            file_path = Path(str(result.get("audio_path", "")))
            label = str(result.get("label", file_path.stem or f"Result {index + 1}"))
            seed = result.get("seed", None)
            duration_ms = int(result.get("duration_ms", 0) or 0)
            favorite = bool(result.get("favorite", False))
            loop_enabled = bool(result.get("loop", False))
            metadata = dict(result.get("metadata", {}) or {})
            output_format = str(result.get("output_format", metadata.get("output_format", "wav")) or "wav").upper()
            output_sample_rate = result.get("output_sample_rate", metadata.get("output_sample_rate", None))
            sample_rate_text = "--"
            if isinstance(output_sample_rate, int) and output_sample_rate > 0:
                sample_rate_text = f"{output_sample_rate / 1000.0:.1f}kHz"
            seed_text = str(seed) if seed is not None else "auto"

            row = QFrame()
            row.setFrameShape(QFrame.Shape.StyledPanel)
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(6, 4, 6, 4)
            row_layout.setSpacing(4)

            header = QHBoxLayout()
            title = QLabel(label)
            title.setStyleSheet("font-weight:700; color:#dde1e7;")
            header.addWidget(title)
            header.addStretch()
            meta = QLabel(f"Seed {seed_text} • {duration_ms / 1000.0:.1f}s • {output_format} • {sample_rate_text}")
            meta.setStyleSheet("color:#8aa0b3; font-size:11px;")
            header.addWidget(meta)
            row_layout.addLayout(header)

            waveform = QLabel(self._render_waveform_ascii_for_file(file_path, columns=28))
            waveform.setStyleSheet("font-family:Consolas, monospace; color:#63d8ff;")
            waveform.setWordWrap(False)
            row_layout.addWidget(waveform)

            button_row = QHBoxLayout()
            play_btn = QPushButton("Play")
            play_btn.clicked.connect(lambda _=False, n=index: self._toggle_ace_step_result_playback(n))
            button_row.addWidget(play_btn)
            loop_btn = QPushButton("Loop On" if loop_enabled else "Loop Off")
            loop_btn.clicked.connect(lambda _=False, n=index: self._toggle_ace_step_result_loop(n))
            button_row.addWidget(loop_btn)
            favorite_btn = QPushButton("★" if favorite else "☆")
            favorite_btn.clicked.connect(lambda _=False, n=index: self._toggle_ace_step_result_favorite(n))
            button_row.addWidget(favorite_btn)
            transfer_btn = QPushButton("To Tracks")
            transfer_btn.clicked.connect(lambda _=False, n=index: self._transfer_ace_step_result(n))
            button_row.addWidget(transfer_btn)
            demucs_btn = QPushButton("To Demucs")
            demucs_btn.clicked.connect(lambda _=False, n=index: self._send_ace_step_result_to_demucs(n))
            button_row.addWidget(demucs_btn)
            button_row.addStretch()
            row_layout.addLayout(button_row)

            volume_row = QHBoxLayout()
            volume_row.addWidget(QLabel("Volume"))
            volume_dial = QDial()
            volume_dial.setRange(0, 100)
            volume_dial.setFixedSize(36, 36)
            volume_dial.setNotchesVisible(True)
            volume_dial.setValue(int(round(float(result.get("volume", 0.7)) * 100.0)))
            volume_dial.valueChanged.connect(lambda value, n=index: self._set_ace_step_result_volume(n, int(value)))
            volume_row.addWidget(volume_dial)
            volume_row.addWidget(QLabel(self._format_file_size(file_path) if file_path.exists() else "missing"))
            volume_row.addStretch()
            row_layout.addLayout(volume_row)

            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.ace_results_list.addItem(item)
            self.ace_results_list.setItemWidget(item, row)

    def _set_ace_step_result_volume(self, result_index: int, dial_value: int) -> None:
        results = getattr(self, "_ace_step_results", [])
        if 0 <= result_index < len(results):
            results[result_index]["volume"] = max(0.0, min(1.0, float(dial_value) / 100.0))

    def _toggle_ace_step_result_playback(self, result_index: Optional[int] = None) -> None:
        results = getattr(self, "_ace_step_results", [])
        if result_index is None:
            result_index = self._selected_ace_step_result_index()
        if result_index is None:
            return
        if not (0 <= result_index < len(results)):
            return
        result = results[result_index]
        file_path = Path(str(result.get("audio_path", "")))
        if not file_path.exists():
            QMessageBox.warning(self, "ACE-Step Preview", f"Result file not found:\n{file_path}")
            return
        if self._ace_step_playing_path == str(file_path):
            self._stop_ace_step_preview_playback()
            return
        try:
            import sounddevice as sd  # type: ignore
            audio, sample_rate = sf.read(str(file_path), always_2d=True)
            gain = float(result.get("volume", 0.7))
            preview = np.asarray(audio, dtype=np.float32) * max(0.0, min(1.0, gain))
            sd.stop()
            sd.play(preview, int(sample_rate), blocking=False)
            self._ace_step_playing_path = str(file_path)
            self.update_status(f"Previewing ACE-Step result: {Path(file_path).name}")
        except Exception as exc:
            QMessageBox.warning(self, "ACE-Step Preview", f"Could not preview result:\n{exc}")

    def _stop_ace_step_preview_playback(self) -> None:
        try:
            import sounddevice as sd  # type: ignore
            sd.stop()
        except Exception:
            pass
        self._ace_step_playing_path = None

    def _toggle_ace_step_result_loop(self, result_index: Optional[int] = None) -> None:
        results = getattr(self, "_ace_step_results", [])
        if result_index is None:
            result_index = self._selected_ace_step_result_index()
        if result_index is None:
            return
        if 0 <= result_index < len(results):
            results[result_index]["loop"] = not bool(results[result_index].get("loop", False))
            self._refresh_ace_step_results()

    def _toggle_ace_step_result_favorite(self, result_index: Optional[int] = None) -> None:
        results = getattr(self, "_ace_step_results", [])
        if result_index is None:
            result_index = self._selected_ace_step_result_index()
        if result_index is None:
            return
        if 0 <= result_index < len(results):
            results[result_index]["favorite"] = not bool(results[result_index].get("favorite", False))
            self._refresh_ace_step_results()

    def _selected_ace_step_result_index(self) -> Optional[int]:
        if not hasattr(self, "ace_results_list"):
            return None
        item = self.ace_results_list.currentItem()
        if item is None:
            return None
        try:
            return int(item.data(Qt.ItemDataRole.UserRole))
        except Exception:
            return None

    def _transfer_ace_step_result(self, result_index: Optional[int] = None) -> None:
        results = getattr(self, "_ace_step_results", [])
        if result_index is None:
            result_index = self._selected_ace_step_result_index()
        if result_index is None or not (0 <= result_index < len(results)):
            QMessageBox.information(self, "Transfer Result", "Select an ACE-Step result first.")
            return

        result = results[result_index]
        file_path = Path(str(result.get("audio_path", "")))
        if not file_path.exists():
            QMessageBox.warning(self, "Transfer Result", f"Result file not found:\n{file_path}")
            return

        if hasattr(self, "ace_transfer_copy_checkbox") and self.ace_transfer_copy_checkbox.isChecked():
            target_root = self._project_folder_for_transfer() / str(self.ace_transfer_subfolder_input.text() or "generated").strip()
            target_root.mkdir(parents=True, exist_ok=True)
            try:
                copied_path = target_root / file_path.name
                shutil.copy2(str(file_path), str(copied_path))
                result["copied_path"] = str(copied_path)
            except Exception:
                pass

        if hasattr(self, "ace_transfer_main_tracks_checkbox") and self.ace_transfer_main_tracks_checkbox.isChecked():
            pre_count = len(self.current_project.tracks)
            track_name = str(result.get("label", file_path.stem)).strip() or file_path.stem
            existing_clip = next((clip for clip in self.current_project.clips if str(getattr(clip, "file_path", "")) == str(file_path)), None)
            if existing_clip is None:
                new_track_index = len(self.current_project.tracks)
                self.current_project.tracks.append(Track(name=track_name))
                new_clip = Clip(
                    id=self.next_clip_id,
                    track_index=new_track_index,
                    file_path=str(file_path),
                    start_ms=0,
                    length_ms=int(result.get("duration_ms", 0) or get_audio_length_ms(str(file_path))),
                )
                self.current_project.clips.append(new_clip)
                self.next_clip_id += 1
                existing_clip = new_clip
            insert_mode = str(self.ace_transfer_insert_combo.currentData() or "append").strip().lower() if hasattr(self, "ace_transfer_insert_combo") else "append"
            if insert_mode == "top":
                total_tracks = len(self.current_project.tracks)
                if total_tracks > pre_count:
                    order = list(range(pre_count, total_tracks)) + list(range(0, pre_count))
                    remap = {old_idx: new_idx for new_idx, old_idx in enumerate(order)}
                    self.current_project.tracks = [self.current_project.tracks[idx] for idx in order]
                    for clip in self.current_project.clips:
                        original = int(getattr(clip, "track_index", 0))
                        if original in remap:
                            clip.track_index = int(remap[original])
            if hasattr(self, "ace_transfer_auto_color_checkbox") and self.ace_transfer_auto_color_checkbox.isChecked():
                result_key = track_name.lower()
                color_map = {
                    "vocals": "#f36f9f",
                    "drums": "#f6bd60",
                    "bass": "#4dd7ff",
                    "guitar": "#7fd29c",
                    "piano": "#b79cff",
                    "other": "#9aa7b6",
                }
                if result_key in color_map and self.current_project.tracks:
                    self.current_project.tracks[existing_clip.track_index].color_hex = color_map[result_key]
            self.sync_project_tracks_to_recording_engine()
            self.refresh_track_list()
            self.refresh_timeline()

        self.update_status(f"Transferred ACE-Step result: {Path(file_path).name}")

    def _sync_transfer_options_between_ace_and_stems(self, source: str) -> None:
        if bool(getattr(self, "_syncing_transfer_options", False)):
            return
        self._syncing_transfer_options = True
        try:
            source_name = str(source or "ace").strip().lower()
            if source_name == "ace":
                if hasattr(self, "ace_transfer_insert_combo") and hasattr(self, "stem_transfer_insert_combo"):
                    ace_insert = str(self.ace_transfer_insert_combo.currentData() or "append").strip().lower()
                    stem_idx = self.stem_transfer_insert_combo.findData(ace_insert)
                    if stem_idx >= 0:
                        self.stem_transfer_insert_combo.setCurrentIndex(stem_idx)
                if hasattr(self, "ace_transfer_auto_color_checkbox") and hasattr(self, "stem_transfer_auto_color_checkbox"):
                    self.stem_transfer_auto_color_checkbox.setChecked(bool(self.ace_transfer_auto_color_checkbox.isChecked()))
                if hasattr(self, "ace_transfer_copy_checkbox") and hasattr(self, "stem_transfer_save_checkbox"):
                    self.stem_transfer_save_checkbox.setChecked(bool(self.ace_transfer_copy_checkbox.isChecked()))
                if hasattr(self, "ace_transfer_subfolder_input") and hasattr(self, "stem_transfer_subfolder_input"):
                    self.stem_transfer_subfolder_input.setText(str(self.ace_transfer_subfolder_input.text() or "generated"))
                return

            if hasattr(self, "stem_transfer_insert_combo") and hasattr(self, "ace_transfer_insert_combo"):
                stem_insert = str(self.stem_transfer_insert_combo.currentData() or "append").strip().lower()
                ace_idx = self.ace_transfer_insert_combo.findData(stem_insert)
                if ace_idx >= 0:
                    self.ace_transfer_insert_combo.setCurrentIndex(ace_idx)
            if hasattr(self, "stem_transfer_auto_color_checkbox") and hasattr(self, "ace_transfer_auto_color_checkbox"):
                self.ace_transfer_auto_color_checkbox.setChecked(bool(self.stem_transfer_auto_color_checkbox.isChecked()))
            if hasattr(self, "stem_transfer_save_checkbox") and hasattr(self, "ace_transfer_copy_checkbox"):
                self.ace_transfer_copy_checkbox.setChecked(bool(self.stem_transfer_save_checkbox.isChecked()))
            if hasattr(self, "stem_transfer_subfolder_input") and hasattr(self, "ace_transfer_subfolder_input"):
                self.ace_transfer_subfolder_input.setText(str(self.stem_transfer_subfolder_input.text() or "stems"))
        finally:
            self._syncing_transfer_options = False

    def _send_ace_step_result_to_demucs(self, result_index: Optional[int] = None) -> None:
        results = getattr(self, "_ace_step_results", [])
        if result_index is None:
            result_index = self._selected_ace_step_result_index()
        if result_index is None or not (0 <= result_index < len(results)):
            QMessageBox.information(self, "Transfer to Demucs", "Select an ACE-Step result first.")
            return
        result = results[result_index]
        file_path = Path(str(result.get("audio_path", "")))
        if not file_path.exists():
            QMessageBox.warning(self, "Transfer to Demucs", f"Result file not found:\n{file_path}")
            return

        self._sync_transfer_options_between_ace_and_stems("ace")

        result_metadata = dict(result.get("metadata", {}) or {})
        output_format = str(result.get("output_format", result_metadata.get("output_format", "")) or "").strip().lower()
        output_sample_rate = result.get("output_sample_rate", result_metadata.get("output_sample_rate", None))
        if hasattr(self, "stem_output_format_combo") and output_format:
            format_idx = self.stem_output_format_combo.findText(output_format, Qt.MatchFlag.MatchFixedString)
            if format_idx >= 0:
                self.stem_output_format_combo.setCurrentIndex(format_idx)
        if hasattr(self, "stem_output_sample_rate_combo") and isinstance(output_sample_rate, int):
            sample_idx = self.stem_output_sample_rate_combo.findData(int(output_sample_rate))
            if sample_idx >= 0:
                self.stem_output_sample_rate_combo.setCurrentIndex(sample_idx)

        if hasattr(self, "stem_source_input"):
            self.stem_source_input.setText(str(file_path))
        self.stem_source_path = file_path
        self._refresh_stem_section_state()
        self._switch_to_tab("Stem Separation")
        self.update_status(f"Sent ACE-Step result to Demucs: {file_path.name}")

    def _choose_ace_audio_reference_upload(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Audio Reference",
            str(self._project_folder_for_transfer()),
            "Audio Files (*.wav *.flac *.mp3 *.ogg *.m4a *.aiff);;All Files (*)",
        )
        if not file_path:
            return
        self.ace_audio_reference_upload_path = Path(file_path)
        if hasattr(self, "ace_audio_reference_source_combo"):
            self.ace_audio_reference_source_combo.setCurrentText("Upload")
        self._refresh_ace_audio_reference_preview()
        self.update_status(f"ACE-Step audio reference selected: {Path(file_path).name}")

    def _resolve_ace_audio_reference_path(self, source: str) -> Optional[Path]:
        source_name = str(source or "None")
        if source_name == "Upload":
            return getattr(self, "ace_audio_reference_upload_path", None)
        if source_name == "Active Track":
            track_index = self.get_selected_track_index() if hasattr(self, "get_selected_track_index") else self.selected_track_index
            if track_index is not None and 0 <= int(track_index) < len(self.current_project.tracks):
                clips = [clip for clip in self.current_project.clips if int(getattr(clip, "track_index", -1)) == int(track_index)]
                if clips:
                    return Path(str(clips[0].file_path))
            return None
        if source_name == "Last Demucs Stem":
            return self.stem_source_path if self.stem_source_path is not None else None
        return None

    def _ace_step_reference_trim_metadata(self, *, validate: bool) -> Optional[dict]:
        source = "None"
        if hasattr(self, "ace_audio_reference_source_combo"):
            source = str(self.ace_audio_reference_source_combo.currentText() or "None")
        reference_path = self._resolve_ace_audio_reference_path(source)

        start_text = str(self.ace_audio_reference_start.text()).strip() if hasattr(self, "ace_audio_reference_start") else ""
        end_text = str(self.ace_audio_reference_end.text()).strip() if hasattr(self, "ace_audio_reference_end") else ""

        def parse_time_or_zero(raw: str, label: str) -> Optional[float]:
            if not raw:
                return 0.0
            try:
                parsed = float(raw)
            except ValueError:
                if validate:
                    QMessageBox.warning(self, "Audio Reference", f"{label} must be a number in seconds.")
                return None
            if parsed < 0.0:
                if validate:
                    QMessageBox.warning(self, "Audio Reference", f"{label} cannot be negative.")
                return None
            return parsed

        start_sec = parse_time_or_zero(start_text, "Reference start")
        end_sec = parse_time_or_zero(end_text, "Reference end")
        if start_sec is None or end_sec is None:
            return None

        if end_sec > 0.0 and end_sec < start_sec:
            if validate:
                QMessageBox.warning(self, "Audio Reference", "Reference end must be greater than or equal to start.")
                return None
            start_sec, end_sec = end_sec, start_sec

        range_text = "Full reference"
        if end_sec > 0.0 and end_sec >= start_sec:
            range_text = f"{start_sec:.2f}s - {end_sec:.2f}s"
        elif start_sec > 0.0:
            range_text = f"{start_sec:.2f}s - end"

        return {
            "source": source,
            "path": str(reference_path) if reference_path is not None else "",
            "start_sec": float(start_sec),
            "end_sec": float(end_sec),
            "range_text": range_text,
            "has_reference": bool(reference_path is not None),
        }

    def _refresh_ace_audio_reference_preview(self) -> None:
        if not hasattr(self, "ace_audio_reference_thumbnail"):
            return
        source = "None"
        if hasattr(self, "ace_audio_reference_source_combo"):
            source = str(self.ace_audio_reference_source_combo.currentText() or "None")
        trim_info = self._ace_step_reference_trim_metadata(validate=False)
        range_text = "Full reference"
        if isinstance(trim_info, dict):
            range_text = str(trim_info.get("range_text", "Full reference"))
        reference_path = self._resolve_ace_audio_reference_path(source)

        if reference_path is None:
            self.ace_audio_reference_thumbnail.setText(
                f"Reference source: {source}\nRange: {range_text}\nNo file selected"
            )
            return

        try:
            waveform = self._render_waveform_ascii_for_file(reference_path, columns=26)
        except Exception:
            waveform = "-" * 26
        self.ace_audio_reference_thumbnail.setText(
            f"Reference source: {source}\nRange: {range_text}\n{reference_path.name}\n{waveform}"
        )

    def _append_ace_step_log(self, message: str) -> None:
        if hasattr(self, "ace_activity_log"):
            self.ace_activity_log.append(message)

    def _clear_ace_step_log(self) -> None:
        if hasattr(self, "ace_activity_log"):
            self.ace_activity_log.clear()

    def _copy_ace_step_log(self) -> None:
        if not hasattr(self, "ace_activity_log"):
            return
        QApplication.clipboard().setText(self.ace_activity_log.toPlainText())

    def _save_ace_step_log(self) -> None:
        if not hasattr(self, "ace_activity_log"):
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save ACE-Step Log",
            str(self._project_folder_for_transfer() / "ace_step_log.txt"),
            "Text Files (*.txt);;All Files (*)",
        )
        if not file_path:
            return
        try:
            Path(file_path).write_text(self.ace_activity_log.toPlainText(), encoding="utf-8")
            self.update_status(f"Saved ACE-Step log to {Path(file_path).name}")
        except Exception as exc:
            QMessageBox.warning(self, "Save ACE-Step Log", f"Could not save log:\n{exc}")

    def _ace_step_seed_value(self) -> Optional[int]:
        if not hasattr(self, "ace_seed_input"):
            return None
        text = self.ace_seed_input.text().strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    def _ace_step_randomize_seed(self) -> int:
        seed = int(time.time() * 1000) % 1_000_000_000
        if hasattr(self, "ace_seed_input"):
            self.ace_seed_input.setText(str(seed))
        if hasattr(self, "ace_lock_seed_checkbox"):
            self.ace_lock_seed_checkbox.setChecked(True)
        return seed

    def _apply_ace_step_result_metadata_to_controls(self, result: dict) -> None:
        metadata = dict(result.get("metadata", {}) or {})

        output_format = str(result.get("output_format", metadata.get("output_format", "")) or "").strip().lower()
        if output_format and hasattr(self, "ace_output_format_combo"):
            format_idx = self.ace_output_format_combo.findText(output_format, Qt.MatchFlag.MatchFixedString)
            if format_idx >= 0:
                self.ace_output_format_combo.setCurrentIndex(format_idx)

        output_sample_rate = result.get("output_sample_rate", metadata.get("output_sample_rate", None))
        if isinstance(output_sample_rate, int) and hasattr(self, "ace_output_sample_rate_combo"):
            sample_idx = self.ace_output_sample_rate_combo.findData(int(output_sample_rate))
            if sample_idx >= 0:
                self.ace_output_sample_rate_combo.setCurrentIndex(sample_idx)

        if hasattr(self, "ace_normalize_checkbox") and "normalize_output" in metadata:
            self.ace_normalize_checkbox.setChecked(bool(metadata.get("normalize_output", True)))

        payload = dict(metadata.get("generation_payload", {}) or {})
        audio_reference = dict(payload.get("audio_reference", {}) or {})
        if audio_reference:
            source = str(audio_reference.get("source", "None") or "None")
            ref_path = str(audio_reference.get("path", "") or "").strip()
            if source == "Upload" and ref_path:
                self.ace_audio_reference_upload_path = Path(ref_path)
            if hasattr(self, "ace_audio_reference_source_combo"):
                source_idx = self.ace_audio_reference_source_combo.findText(source, Qt.MatchFlag.MatchFixedString)
                if source_idx >= 0:
                    self.ace_audio_reference_source_combo.setCurrentIndex(source_idx)
            if hasattr(self, "ace_audio_reference_start"):
                self.ace_audio_reference_start.setText(f"{float(audio_reference.get('start_sec', 0.0)):.2f}")
            if hasattr(self, "ace_audio_reference_end"):
                self.ace_audio_reference_end.setText(f"{float(audio_reference.get('end_sec', 0.0)):.2f}")
            influence = audio_reference.get("influence_strength", None)
            if influence is not None and hasattr(self, "ace_audio_reference_strength"):
                try:
                    self.ace_audio_reference_strength.setValue(float(influence))
                except (TypeError, ValueError):
                    pass
            self._refresh_ace_audio_reference_preview()

    def _ace_step_run_quick_action(self, action: str, result_index: Optional[int] = None) -> None:
        results = getattr(self, "_ace_step_results", [])
        if result_index is None:
            result_index = self._selected_ace_step_result_index()
        if result_index is None or not (0 <= result_index < len(results)):
            QMessageBox.information(self, "ACE-Step Action", "Select an ACE-Step result first.")
            return

        result = results[result_index]
        self._apply_ace_step_result_metadata_to_controls(result)
        base_prompt = str(result.get("prompt", "")).strip() or self.ace_prompt_input.toPlainText().strip()
        base_lyrics = str(result.get("lyrics", "")).strip() or self.ace_lyrics_input.toPlainText().strip()

        if action == "same":
            seed = result.get("seed")
            if seed is not None and hasattr(self, "ace_seed_input"):
                self.ace_seed_input.setText(str(seed))
            if hasattr(self, "ace_lock_seed_checkbox"):
                self.ace_lock_seed_checkbox.setChecked(True)
            if base_prompt:
                self.ace_prompt_input.setPlainText(base_prompt)
            if base_lyrics:
                self.ace_lyrics_input.setPlainText(base_lyrics)
        elif action == "new":
            self._ace_step_randomize_seed()
            if base_prompt:
                self.ace_prompt_input.setPlainText(base_prompt)
            if base_lyrics:
                self.ace_lyrics_input.setPlainText(base_lyrics)
        elif action == "subtle":
            if base_prompt:
                self.ace_prompt_input.setPlainText(
                    f"{base_prompt}\n\nSubtle variation: keep the core structure, but refine textures, dynamics, and mix detail."
                )
            self._ace_step_randomize_seed()
        elif action == "strong":
            if base_prompt:
                self.ace_prompt_input.setPlainText(
                    f"{base_prompt}\n\nStrong variation: reinterpret the idea with a new arrangement, stronger contrast, and bolder timbral changes."
                )
            self._ace_step_randomize_seed()
        else:
            return

        if hasattr(self, "ace_generate_btn"):
            self.ace_generate_btn.click()

    def _set_ace_step_processing_state(self, processing: bool) -> None:
        self._ace_step_is_processing = bool(processing)
        if hasattr(self, "ace_generate_btn"):
            processing_label = "Generating..."
            if processing and hasattr(self, "ace_estimated_time_label"):
                estimate_text = str(self.ace_estimated_time_label.text() or "").replace("Est. time:", "").strip()
                if estimate_text:
                    processing_label = f"Generating... ({estimate_text})"
            self.ace_generate_btn.setEnabled(not processing)
            self.ace_generate_btn.setText("Generate" if not processing else processing_label)
        if hasattr(self, "ace_transfer_btn"):
            self.ace_transfer_btn.setEnabled(not processing and bool(getattr(self, "_ace_step_results", [])))
        if hasattr(self, "ace_activity_state_label"):
            self.ace_activity_state_label.setText("Processing" if processing else "Idle")
            self.ace_activity_state_label.setStyleSheet(
                "color:#f2b84b; font-weight:700;" if processing else "color:#8aa0b3; font-weight:600;"
            )

        if processing:
            self._ace_step_pulse_state = False
            self._apply_ace_step_processing_button_style()
            if not hasattr(self, "_ace_step_pulse_timer"):
                self._ace_step_pulse_timer = QTimer(self)
                self._ace_step_pulse_timer.setInterval(360)
                self._ace_step_pulse_timer.timeout.connect(self._on_ace_step_processing_pulse)
            self._ace_step_pulse_timer.start()
            return

        if hasattr(self, "_ace_step_pulse_timer"):
            self._ace_step_pulse_timer.stop()
        self._apply_ace_step_processing_button_style()

    def _apply_ace_step_processing_button_style(self) -> None:
        if not hasattr(self, "ace_generate_btn"):
            return
        if not bool(self._ace_step_is_processing):
            self.ace_generate_btn.setStyleSheet(
                "QPushButton { background:#177b4d; color:#eefaf2; border:1px solid #1f9a63; border-radius:4px; "
                "font-weight:700; padding:6px 10px; }"
                "QPushButton:hover { background:#1c8a58; }"
                "QPushButton:disabled { background:#1f3a2f; color:#87a291; border:1px solid #2d4a3d; }"
            )
            return
        active_bg = "#a0621e" if self._ace_step_pulse_state else "#8b4f18"
        active_border = "#ffc062" if self._ace_step_pulse_state else "#d69a48"
        self.ace_generate_btn.setStyleSheet(
            "QPushButton {"
            f"background:{active_bg}; color:#fff2e0; border:1px solid {active_border}; border-radius:4px; "
            "font-weight:700; padding:6px 10px; }"
            "QPushButton:disabled { color:#fff2e0; }"
        )

    def _on_ace_step_processing_pulse(self) -> None:
        if not bool(self._ace_step_is_processing):
            return
        self._ace_step_pulse_state = not bool(self._ace_step_pulse_state)
        self._apply_ace_step_processing_button_style()

    def _populate_stem_transfer_checklist(self) -> None:
        self._get_stem_workflow_controller().populate_stem_transfer_checklist()

    def _checked_stem_names(self) -> list[str]:
        return self._get_stem_workflow_controller().checked_stem_names()

    def _copy_selected_stems_to_project_folder(self, stem_names: list[str]) -> Optional[Path]:
        return self._get_stem_workflow_controller().copy_selected_stems_to_project_folder(stem_names)

    def _transfer_selected_stems_to_project(self) -> None:
        self._get_stem_workflow_controller().transfer_selected_stems_to_project()

    def _send_selected_stem_to_ace_step(self) -> None:
        self._get_stem_workflow_controller().send_selected_stem_to_ace_step()

    def _update_stem_backend_summary(self) -> None:
        self._get_stem_workflow_controller().update_stem_backend_summary()

    def _refresh_stem_device_indicator(self) -> None:
        self._get_stem_workflow_controller().refresh_stem_device_indicator()

    def _set_stem_processing_state(self, processing: bool) -> None:
        self._get_stem_workflow_controller().set_stem_processing_state(processing)

    def _apply_stem_processing_button_style(self) -> None:
        self._get_stem_workflow_controller().apply_stem_processing_button_style()

    def _on_stem_processing_pulse(self) -> None:
        self._get_stem_workflow_controller().on_stem_processing_pulse()

    def _refresh_stem_section_state(self) -> None:
        self._get_stem_workflow_controller().refresh_stem_section_state()

    def _clear_stem_worker(self) -> None:
        self._get_stem_workflow_controller().clear_stem_worker()

    def _on_stem_worker_progress(self, message: str) -> None:
        self._get_stem_workflow_controller().on_stem_worker_progress(message)

    def _on_stem_worker_completed(self, payload: dict) -> None:
        self._get_stem_workflow_controller().on_stem_worker_completed(payload)

    def _on_stem_worker_cancelled(self, message: str) -> None:
        self._get_stem_workflow_controller().on_stem_worker_cancelled(message)

    def _on_stem_worker_failed(self, error_kind: str, message: str) -> None:
        self._get_stem_workflow_controller().on_stem_worker_failed(error_kind, message)

    def _start_stem_separation_worker(self, song_path: Path) -> None:
        if self._stem_is_processing:
            self.update_status("Stem separation is already running")
            return
        if not song_path.exists() or not song_path.is_file():
            QMessageBox.warning(self, "Stems", "Selected source audio does not exist.")
            return

        self._set_stem_source_path(song_path)
        model_name = self._selected_demucs_model()
        output_dir = song_path.parent / "echo_stems" / song_path.stem
        self._latest_stem_results = {}
        self._latest_stem_output_dir = output_dir
        self._stop_stem_preview_playback()
        self._populate_stem_transfer_checklist()
        self._refresh_stem_preview_rows()
        if hasattr(self, "stem_transfer_btn"):
            self.stem_transfer_btn.setEnabled(False)
        if hasattr(self, "stem_to_ace_btn"):
            self.stem_to_ace_btn.setEnabled(False)
        self._reset_stem_progress_ui(state_text="Loading model...")
        self._set_stem_status(
            f"Preparing Demucs split with {model_name}.",
            detail=f"Source: {song_path.name}",
            reset_activity=True,
        )
        self.update_status("Running Demucs... this may take a while.")

        self._stem_worker_thread = QThread(self)
        self._stem_worker = StemSeparationWorker(source_path=song_path, output_dir=output_dir, model_name=model_name)
        self._stem_worker.moveToThread(self._stem_worker_thread)

        self._stem_worker_thread.started.connect(self._stem_worker.run)
        self._stem_worker.progress.connect(self._on_stem_worker_progress)
        self._stem_worker.completed.connect(self._on_stem_worker_completed)
        self._stem_worker.failed.connect(self._on_stem_worker_failed)
        self._stem_worker.cancelled.connect(self._on_stem_worker_cancelled)

        self._set_stem_processing_state(True)
        self._stem_worker_thread.start()

    def cancel_selected_stem_split(self) -> None:
        self._get_stem_workflow_controller().cancel_selected_stem_split()

    def _set_stem_source_path(self, song_path: Optional[Path]) -> None:
        self._get_stem_workflow_controller().set_stem_source_path(song_path)

    def _on_stem_source_dropped(self, song_path: Path) -> None:
        self._get_stem_workflow_controller().on_stem_source_dropped(song_path)

    def _show_demucs_model_manager_placeholder(self) -> None:
        self._get_stem_workflow_controller().show_demucs_model_manager_placeholder()

    def choose_stem_source_audio(self) -> None:
        self._get_stem_workflow_controller().choose_stem_source_audio()

    def _selected_demucs_model(self) -> str:
        return self._get_stem_workflow_controller().selected_demucs_model()

    def run_selected_stem_split(self) -> None:
        self._get_stem_workflow_controller().run_selected_stem_split()

    def _build_recording_meters(self):
        while self.meter_container.count():
            item = self.meter_container.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.recording_meters = {}
        for track in self.recording_controller.engine.tracks:
            if track.track_id < len(self.current_project.tracks):
                meter_name = self.current_project.tracks[track.track_id].name
            else:
                meter_name = f"Track {track.track_id + 1}"
            meter = TrackMeterWidget(meter_name)
            self.meter_container.addWidget(meter)
            self.recording_meters[track.track_id] = meter

    def sync_project_tracks_to_recording_engine(self):
        for idx, project_track in enumerate(self.current_project.tracks):
            self._enforce_track_runtime_policy(idx, project_track)
            engine_track = self.recording_controller.engine.get_track(idx)
            if engine_track is None:
                continue
            engine_track.name = project_track.name
            engine_track.set_volume_db(project_track.volume_db)
            engine_track.pan = float(getattr(project_track, "pan", 0.0))
            engine_track.muted = project_track.muted
            engine_track.soloed = project_track.soloed

        for idx in range(len(self.current_project.tracks), len(self.recording_controller.engine.tracks)):
            engine_track = self.recording_controller.engine.get_track(idx)
            if engine_track is None:
                continue
            engine_track.name = f"Track {idx + 1}"
            engine_track.set_volume_db(0.0)
            engine_track.muted = False
            engine_track.soloed = False

    def refresh_track_list(self):
        self.track_list.blockSignals(True)
        self.track_list.clear()

        armed = set(self.recording_controller.status.active_track_ids)
        for idx, track in enumerate(self.current_project.tracks):
            flags = []
            if track.muted:
                flags.append("M")
            if track.soloed:
                flags.append("S")
            playback_settings = track.playback_settings
            if playback_settings.loop_enabled:
                flags.append("L")
            if playback_settings.fade_in_ms > 0 or playback_settings.fade_out_ms > 0:
                flags.append("F")
            if self._count_enabled_track_effects(track) > 0:
                flags.append("FX")
            if idx in armed:
                flags.append("A")

            flag_text = f" [{' '.join(flags)}]" if flags else ""
            track_type = str(getattr(track, "track_type", "Audio") or "Audio")
            type_text = f" [{track_type}]" if track_type != "Audio" else ""
            self.track_list.addItem(f"{idx}: {track.name}{type_text} ({track.volume_db:.1f} dB){flag_text}")

        row = -1
        if self.current_project.tracks:
            if self.selected_track_index is None:
                row = 0
            else:
                row = min(self.selected_track_index, len(self.current_project.tracks) - 1)

        self.selected_track_index = row if row >= 0 else None
        if row >= 0:
            self.track_list.setCurrentRow(row)

        self.track_list.blockSignals(False)
        self.refresh_take_track_selector()
        self.on_track_selection_changed(self.selected_track_index if self.selected_track_index is not None else -1)

    def on_track_selection_changed(self, row: int):
        if row < 0 or row >= len(self.current_project.tracks):
            self.selected_track_index = None
            self.timeline.set_selected_track(None)
            return

        self.selected_track_index = row
        self.timeline.set_selected_track(row)

        # Keep index-based controls in sync with list selection.
        self.clip_track_index_input.setText(str(row))
        self.volume_track_index_input.setText(str(row))
        self.voice_track_index_input.setText(str(row))
        self.record_track_input.setText(str(row))
        self.track_name_input.setText(self.current_project.tracks[row].name)

        combo_index = self.take_track_combo.findData(row)
        if combo_index >= 0:
            self.take_track_combo.setCurrentIndex(combo_index)
        else:
            self.refresh_take_review_list()

        self._sync_timeline_automation_target_for_track(int(row))

    def _on_timeline_track_selected(self, track_index: int) -> None:
        if track_index < 0 or track_index >= len(self.current_project.tracks):
            return
        if self.track_list.currentRow() != int(track_index):
            self.track_list.setCurrentRow(int(track_index))
            return
        self.on_track_selection_changed(int(track_index))

    def _on_timeline_track_double_click(self, track_index: int) -> None:
        if not (0 <= int(track_index) < len(self.current_project.tracks)):
            return
        self.selected_track_index = int(track_index)
        if hasattr(self, "track_list") and self.track_list.currentRow() != int(track_index):
            self.track_list.setCurrentRow(int(track_index))
        open_editor = getattr(self, "open_single_track_editor", None)
        if callable(open_editor):
            open_editor(int(track_index))

    def _clip_fade_state(self, clip: Clip) -> Tuple[int, int, str, str]:
        metadata = dict(getattr(clip, "metadata", {}) or {})
        length_ms = max(1, int(getattr(clip, "length_ms", 1)))
        fade_in_ms = max(0, min(length_ms, int(metadata.get("fade_in_ms", 0) or 0)))
        fade_out_ms = max(0, min(length_ms, int(metadata.get("fade_out_ms", 0) or 0)))
        fade_in_curve = str(metadata.get("fade_in_curve", "Linear") or "Linear")
        fade_out_curve = str(metadata.get("fade_out_curve", "Linear") or "Linear")
        return int(fade_in_ms), int(fade_out_ms), fade_in_curve, fade_out_curve

    def _set_clip_fade_state(
        self,
        clip: Clip,
        *,
        fade_in_ms: int,
        fade_out_ms: int,
        fade_in_curve: str,
        fade_out_curve: str,
    ) -> None:
        metadata = dict(getattr(clip, "metadata", {}) or {})
        length_ms = max(1, int(getattr(clip, "length_ms", 1)))
        metadata["fade_in_ms"] = max(0, min(length_ms, int(fade_in_ms)))
        metadata["fade_out_ms"] = max(0, min(length_ms, int(fade_out_ms)))
        metadata["fade_in_curve"] = str(fade_in_curve or "Linear")
        metadata["fade_out_curve"] = str(fade_out_curve or "Linear")
        clip.metadata = metadata

    def _begin_clip_fade_edit(self, clip_id: int) -> None:
        clip = self._find_clip_by_id(int(clip_id))
        if clip is None:
            return
        current_signature = self._clip_fade_state(clip)
        active = self._clip_fade_edit_state
        if active is not None and int(active.get("clip_id", -1)) == int(clip_id):
            return
        self._clip_fade_edit_state = {
            "clip_id": int(clip_id),
            "snapshot": self._snapshot_project_edit_state(),
            "signature": current_signature,
            "defer_notice_shown": False,
        }

    def _commit_clip_fade_edit(self, clip_id: int, description: str) -> None:
        active = self._clip_fade_edit_state
        clip = self._find_clip_by_id(int(clip_id))
        if active is None or clip is None:
            return
        if int(active.get("clip_id", -1)) != int(clip_id):
            return
        original_signature = tuple(active.get("signature", (0, 0, "Linear", "Linear")))
        if tuple(self._clip_fade_state(clip)) != original_signature:
            self._push_project_snapshot(str(description), active["snapshot"])
        self._clip_fade_edit_state = None

    def _sync_fade_popover_from_clip(self, clip_id: int) -> None:
        if self._clip_fade_popover is None:
            return
        if not self._clip_fade_popover.isVisible() or self._clip_fade_popover.clip_id() != int(clip_id):
            return
        clip = self._find_clip_by_id(int(clip_id))
        if clip is None:
            return
        fade_in_ms, fade_out_ms, fade_in_curve, fade_out_curve = self._clip_fade_state(clip)
        self._clip_fade_popover.set_clip_context(
            int(clip_id),
            fade_in_ms=fade_in_ms,
            fade_out_ms=fade_out_ms,
            fade_in_curve=fade_in_curve,
            fade_out_curve=fade_out_curve,
        )

    def _on_timeline_clip_fade_changed(self, clip_id: int, fade_in_ms: int, fade_out_ms: int, commit: bool) -> None:
        clip = self._find_clip_by_id(int(clip_id))
        if clip is None:
            return
        self._begin_clip_fade_edit(int(clip_id))
        _old_in, _old_out, in_curve, out_curve = self._clip_fade_state(clip)
        self._set_clip_fade_state(
            clip,
            fade_in_ms=int(fade_in_ms),
            fade_out_ms=int(fade_out_ms),
            fade_in_curve=in_curve,
            fade_out_curve=out_curve,
        )
        self._sync_fade_popover_from_clip(int(clip_id))
        if commit:
            self._commit_clip_fade_edit(int(clip_id), f"Clip {clip_id} fade drag")
            self._refresh_active_project_playback_mix(f"clip {clip_id} fades")
            self.update_status(
                f"Clip {clip_id} fades: in {int(fade_in_ms)}ms, out {int(fade_out_ms)}ms"
            )

    def _on_fade_popover_changed(
        self,
        clip_id: int,
        fade_in_ms: int,
        fade_out_ms: int,
        fade_in_curve: str,
        fade_out_curve: str,
    ) -> None:
        clip = self._find_clip_by_id(int(clip_id))
        if clip is None:
            return
        self._begin_clip_fade_edit(int(clip_id))
        self._set_clip_fade_state(
            clip,
            fade_in_ms=int(fade_in_ms),
            fade_out_ms=int(fade_out_ms),
            fade_in_curve=str(fade_in_curve),
            fade_out_curve=str(fade_out_curve),
        )
        active = self._clip_fade_edit_state
        if self._is_project_playback_running() and isinstance(active, dict) and not bool(active.get("defer_notice_shown", False)):
            active["defer_notice_shown"] = True
            self.update_status("Fade popover edits are queued and will apply when you close the popover")
        self.timeline.update()

    def _on_fade_popover_closed(self, clip_id: int) -> None:
        self._commit_clip_fade_edit(int(clip_id), f"Clip {clip_id} fade settings")
        self._refresh_active_project_playback_mix(f"clip {clip_id} fade settings")

    def _show_clip_fade_settings_popover(self, clip_id: int) -> None:
        clip = self._find_clip_by_id(int(clip_id))
        if clip is None:
            QMessageBox.warning(self, "Fade Settings", "The selected clip no longer exists.")
            return

        if self._clip_fade_popover is None:
            self._clip_fade_popover = ClipFadeSettingsPopover(self)
            self._clip_fade_popover.bind(self._on_fade_popover_changed, self._on_fade_popover_closed)

        active_clip_id = self._clip_fade_popover.clip_id()
        if (
            active_clip_id is not None
            and int(active_clip_id) != int(clip_id)
            and self._clip_fade_popover.isVisible()
        ):
            self._commit_clip_fade_edit(int(active_clip_id), f"Clip {active_clip_id} fade settings")

        self._begin_clip_fade_edit(int(clip_id))
        fade_in_ms, fade_out_ms, fade_in_curve, fade_out_curve = self._clip_fade_state(clip)
        self._clip_fade_popover.set_clip_context(
            int(clip_id),
            fade_in_ms=fade_in_ms,
            fade_out_ms=fade_out_ms,
            fade_in_curve=fade_in_curve,
            fade_out_curve=fade_out_curve,
        )
        cursor_pos = QCursor.pos()
        self._clip_fade_popover.move(cursor_pos.x() + 12, cursor_pos.y() + 12)
        self._clip_fade_popover.show()
        self._clip_fade_popover.raise_()
        self._clip_fade_popover.activateWindow()

    def _normalize_automation_parameter_key(self, parameter: str) -> str:
        normalized = str(parameter or "").strip().lower()
        if normalized in {"volume_db", "pan", "send_a", "send_b"}:
            return normalized
        return "volume_db"

    def _track_automation_parameter(self, track_index: int) -> str:
        if not (0 <= int(track_index) < len(self.current_project.tracks)):
            return "volume_db"
        track = self.current_project.tracks[int(track_index)]
        settings = track.playback_settings
        stored = self._automation_parameter_by_track.get(int(track_index))
        if stored is not None:
            return self._normalize_automation_parameter_key(stored)
        meta_value = getattr(settings, "active_automation_parameter", "volume_db")
        selected = self._normalize_automation_parameter_key(str(meta_value or "volume_db"))
        self._automation_parameter_by_track[int(track_index)] = selected
        return selected

    def _track_automation_points(self, track_index: int, parameter: str) -> list[dict]:
        if not (0 <= int(track_index) < len(self.current_project.tracks)):
            return []
        normalized_parameter = self._normalize_automation_parameter_key(parameter)
        track = self.current_project.tracks[int(track_index)]
        automation_map = track.playback_settings.automation
        if not isinstance(automation_map, dict):
            track.playback_settings.automation = {}
            automation_map = track.playback_settings.automation
        points = automation_map.get(normalized_parameter, [])
        if not isinstance(points, list):
            return []
        cleaned_points: list[dict] = []
        for point in points:
            if not isinstance(point, dict):
                continue
            try:
                time_ms = max(0, int(point.get("time_ms", 0)))
                value = max(0.0, min(1.0, float(point.get("value", 0.5))))
            except (TypeError, ValueError):
                continue
            cleaned_points.append({"time_ms": time_ms, "value": value})
        cleaned_points.sort(key=lambda item: int(item["time_ms"]))
        return cleaned_points

    def _set_track_automation_parameter(self, track_index: int, parameter: str) -> None:
        if not (0 <= int(track_index) < len(self.current_project.tracks)):
            return
        normalized_parameter = self._normalize_automation_parameter_key(parameter)
        track = self.current_project.tracks[int(track_index)]
        settings = track.playback_settings
        previous = self._track_automation_parameter(int(track_index))
        if previous == normalized_parameter:
            self._sync_timeline_automation_target_for_track(int(track_index))
            return
        pre_change_snapshot = self._snapshot_project_edit_state()
        self._automation_parameter_by_track[int(track_index)] = normalized_parameter
        settings.active_automation_parameter = normalized_parameter
        self._push_project_snapshot(f"Track {track_index + 1} automation target", pre_change_snapshot)
        self._sync_timeline_automation_target_for_track(int(track_index))
        self.update_status(f"Track {track_index + 1} automation target: {normalized_parameter.replace('_', ' ').title()}")

    def _sync_timeline_automation_target_for_track(self, track_index: int) -> None:
        if not hasattr(self, "timeline"):
            return
        if not (0 <= int(track_index) < len(self.current_project.tracks)):
            return
        parameter = self._track_automation_parameter(int(track_index))
        self.timeline.set_active_automation_parameter(int(track_index), parameter)
        points = self._track_automation_points(int(track_index), parameter)
        self.timeline.set_track_automation_points(int(track_index), parameter, points)

    def _on_track_automation_parameter_changed(self, track_index: int, parameter: str) -> None:
        self._set_track_automation_parameter(int(track_index), str(parameter))

    def _on_timeline_automation_points_changed(self, track_index: int, parameter: str, points: list[dict]) -> None:
        if not (0 <= int(track_index) < len(self.current_project.tracks)):
            return
        normalized_parameter = self._normalize_automation_parameter_key(parameter)
        sanitized_points: list[dict] = []
        for point in points:
            if not isinstance(point, dict):
                continue
            try:
                time_ms = max(0, int(point.get("time_ms", 0)))
                value = max(0.0, min(1.0, float(point.get("value", 0.5))))
            except (TypeError, ValueError):
                continue
            sanitized_points.append({"time_ms": time_ms, "value": value})
        sanitized_points.sort(key=lambda item: int(item["time_ms"]))

        track = self.current_project.tracks[int(track_index)]
        settings = track.playback_settings
        if not isinstance(settings.automation, dict):
            settings.automation = {}
        current_points = self._track_automation_points(int(track_index), normalized_parameter)
        if current_points == sanitized_points:
            return

        pre_change_snapshot = self._snapshot_project_edit_state()
        settings.automation[normalized_parameter] = sanitized_points
        settings.active_automation_parameter = normalized_parameter
        self._automation_parameter_by_track[int(track_index)] = normalized_parameter
        self.timeline.set_track_automation_points(int(track_index), normalized_parameter, sanitized_points)
        self._push_project_snapshot(
            f"Track {track_index + 1} automation {normalized_parameter.replace('_', ' ')}",
            pre_change_snapshot,
        )
        self._refresh_active_project_playback_mix(
            f"track {track_index + 1} automation {normalized_parameter.replace('_', ' ')}"
        )
        self.update_status(f"Automation updated on track {track_index + 1} ({normalized_parameter.replace('_', ' ')})")

    def refresh_take_track_selector(self):
        selected_track_id = self.take_track_combo.currentData()
        if selected_track_id is None:
            selected_track_id = self.selected_track_index

        self.take_track_combo.blockSignals(True)
        self.take_track_combo.clear()

        for idx, track in enumerate(self.current_project.tracks):
            self.take_track_combo.addItem(f"{idx}: {track.name}", idx)

        if self.take_track_combo.count() > 0:
            if selected_track_id is None:
                selected_track_id = 0
            combo_index = self.take_track_combo.findData(selected_track_id)
            self.take_track_combo.setCurrentIndex(combo_index if combo_index >= 0 else 0)

        self.take_track_combo.blockSignals(False)

    def _recording_take_metadata(self, track_id: int, take_number: int) -> Dict[str, object]:
        return {
            "source": "recording_take",
            "session_id": self.recording_controller.session.session_id,
            "track_id": int(track_id),
            "take_number": int(take_number),
        }

    def _collect_take_review_preferences(self) -> Dict[str, object]:
        return {
            "take_filter": self.take_filter_combo.currentData(),
            "take_sort": self.take_sort_combo.currentData(),
            "take_loop": bool(self.take_loop_combo.currentData()),
            "hide_inactive_take_clips": self.hide_inactive_take_clips_btn.isChecked(),
            "take_view_mode": self.take_view_mode_combo.currentData(),
        }

    def _save_take_review_preferences(self) -> None:
        self.recording_controller.session.ui_preferences = self._collect_take_review_preferences()
        self.recording_controller.session.save_session_metadata()

    def _apply_take_review_preferences(self) -> None:
        prefs = dict(getattr(self.recording_controller.session, "ui_preferences", {}) or {})

        sort_index = self.take_sort_combo.findData(prefs.get("take_sort", "newest"))
        if sort_index >= 0:
            self.take_sort_combo.setCurrentIndex(sort_index)

        filter_index = self.take_filter_combo.findData(prefs.get("take_filter", "all"))
        if filter_index >= 0:
            self.take_filter_combo.setCurrentIndex(filter_index)

        loop_index = self.take_loop_combo.findData(bool(prefs.get("take_loop", False)))
        if loop_index >= 0:
            self.take_loop_combo.setCurrentIndex(loop_index)

        view_mode = str(prefs.get("take_view_mode", "expanded"))
        view_mode_index = self.take_view_mode_combo.findData(view_mode)
        if view_mode_index >= 0:
            self.take_view_mode_combo.setCurrentIndex(view_mode_index)
        self.take_list_widget.set_view_mode(view_mode)

        hide_inactive = bool(prefs.get("hide_inactive_take_clips", False))
        self.hide_inactive_take_clips_btn.setChecked(hide_inactive)
        self.timeline.set_hide_inactive_take_clips(hide_inactive)

    def on_take_review_preferences_changed(self, *_args):
        self.take_list_widget.set_view_mode(str(self.take_view_mode_combo.currentData() or "expanded"))
        self._save_take_review_preferences()
        self.refresh_take_review_list()

    def on_hide_inactive_take_clips_toggled(self, checked: bool):
        self.timeline.set_hide_inactive_take_clips(bool(checked))
        self._save_take_review_preferences()
        self.refresh_timeline()

    def _find_take_clip(self, track_id: int, take_number: int):
        for clip in self.current_project.clips:
            metadata = getattr(clip, "metadata", {}) or {}
            if (
                metadata.get("source") == "recording_take"
                and int(metadata.get("track_id", -1)) == int(track_id)
                and int(metadata.get("take_number", -1)) == int(take_number)
            ):
                return clip
        return None

    def _next_timeline_insert_ms(self) -> int:
        if not self.current_project.clips:
            return 0
        return max(clip.start_ms + clip.length_ms for clip in self.current_project.clips)

    def _sync_take_clips_for_track(self, track_id: int) -> None:
        takes = self.recording_controller.get_track_takes(int(track_id))
        if not takes:
            return

        first_existing_take_clip = next(
            (
                clip for clip in self.current_project.clips
                if (getattr(clip, "metadata", {}) or {}).get("source") == "recording_take"
                and int((getattr(clip, "metadata", {}) or {}).get("track_id", -1)) == int(track_id)
            ),
            None,
        )
        clip_start_ms = first_existing_take_clip.start_ms if first_existing_take_clip is not None else self._next_timeline_insert_ms()

        for take in takes:
            clip = self._find_take_clip(track_id, take.take_number)
            if clip is None:
                ok, wav_path, message = self.recording_controller.export_take_to_wav(int(track_id), int(take.take_number))
                if not ok or wav_path is None:
                    self.update_status(f"Take export failed for track {track_id} take {take.take_number}: {message}")
                    continue

                clip = Clip(
                    id=self.next_clip_id,
                    track_index=int(track_id),
                    file_path=str(wav_path),
                    start_ms=clip_start_ms,
                    length_ms=max(1, int(round(take.duration_seconds * 1000.0))),
                    metadata={},
                )
                self.next_clip_id += 1
                self.current_project.clips.append(clip)

            metadata = dict(getattr(clip, "metadata", {}) or {})
            metadata.update(self._recording_take_metadata(track_id, take.take_number))
            metadata["is_active_take"] = bool(take.used)
            metadata["timestamp"] = take.timestamp
            metadata["peak_db"] = float(take.level_stats.get("peak", -80.0))
            metadata["clipping"] = float(take.level_stats.get("clipping", 0.0))
            metadata["is_keeper"] = bool(getattr(take, "is_keeper", False))
            metadata["is_muted_take"] = bool(getattr(take, "is_muted", False))
            metadata["take_rating"] = int(getattr(take, "rating", 0))
            metadata["comp_selected"] = bool(metadata.get("comp_selected", False))
            metadata["comp_region_ids"] = list(metadata.get("comp_region_ids", []))
            clip.metadata = metadata
            clip.track_index = int(track_id)
            clip.length_ms = max(1, int(round(take.duration_seconds * 1000.0)))

        self._apply_comp_preview_metadata(int(track_id))

    def _ranges_overlap(self, a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
        return int(a_start) < int(b_end) and int(b_start) < int(a_end)

    def _find_comp_region_for_range(self, track_id: int, start_ms: int, end_ms: int):
        regions = self.recording_controller.session.get_comp_regions_for_track(int(track_id))
        for region in regions:
            if not bool(region.enabled):
                continue
            if int(region.start_ms) == int(start_ms) and int(region.end_ms) == int(end_ms):
                return region
        return None

    def _apply_comp_preview_metadata(self, track_id: int) -> None:
        comp_regions = [
            region
            for region in self.recording_controller.session.get_comp_regions_for_track(int(track_id))
            if bool(region.enabled)
        ]

        for clip in self.current_project.clips:
            metadata = dict(getattr(clip, "metadata", {}) or {})
            if metadata.get("source") != "recording_take":
                continue
            if int(metadata.get("track_id", -1)) != int(track_id):
                continue

            clip_start = int(clip.start_ms)
            clip_end = int(clip.start_ms + clip.length_ms)
            take_number = int(metadata.get("take_number", -1))

            matching_region_ids = []
            for region in comp_regions:
                if int(region.source_take_number) != take_number:
                    continue
                if self._ranges_overlap(clip_start, clip_end, int(region.start_ms), int(region.end_ms)):
                    matching_region_ids.append(int(region.region_id))

            metadata["comp_selected"] = bool(matching_region_ids)
            metadata["comp_region_ids"] = matching_region_ids
            clip.metadata = metadata

    def _set_active_take_clip_metadata(self, track_id: int, take_number: int) -> None:
        for clip in self.current_project.clips:
            metadata = dict(getattr(clip, "metadata", {}) or {})
            if metadata.get("source") != "recording_take":
                continue
            if int(metadata.get("track_id", -1)) != int(track_id):
                continue
            metadata["is_active_take"] = int(metadata.get("take_number", -1)) == int(take_number)
            clip.metadata = metadata

    def refresh_take_review_list(self, *_args):
        self.take_review_list.clear()
        track_id = self.take_track_combo.currentData()
        if track_id is None:
            return

        takes = self.recording_controller.get_track_takes(int(track_id))
        filter_mode = self.take_filter_combo.currentData()
        if filter_mode == "clipped":
            takes = [t for t in takes if float(t.level_stats.get("clipping", 0.0)) >= 0.5]
        elif filter_mode == "active":
            takes = [t for t in takes if t.used]

        sort_mode = self.take_sort_combo.currentData()
        reverse = sort_mode != "oldest"
        takes = sorted(takes, key=lambda t: t.take_number, reverse=reverse)

        if not takes:
            self.take_review_list.addItem("No takes recorded for this track yet.")
            self.take_review_list.item(0).setFlags(Qt.ItemFlag.NoItemFlags)
            return

        for take in takes:
            peak_db = float(take.level_stats.get("peak", -80.0))
            clipping = float(take.level_stats.get("clipping", 0.0)) >= 0.5
            status = "ACTIVE" if take.used else "inactive"
            timestamp = take.timestamp.replace("T", " ")[:19]
            clip_flag = "CLIP" if clipping else "OK"
            clip_events = int(getattr(take, "clip_events", 0))
            keeper_flag = "KEEP" if bool(getattr(take, "is_keeper", False)) else "----"
            muted_flag = "MUTED" if bool(getattr(take, "is_muted", False)) else "AUD"
            rating = int(getattr(take, "rating", 0))
            note_flag = "NOTE" if str(getattr(take, "notes", "")).strip() else "----"
            text = (
                f"Take {take.take_number} [{status}] | {take.duration_seconds:.2f}s"
                f" | Peak {peak_db:.1f} dB | {clip_flag}({clip_events}) | {keeper_flag} | {muted_flag} | R{rating} | {note_flag} | {timestamp}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, {"track_id": int(track_id), "take_number": take.take_number})
            self.take_review_list.addItem(item)

    def _get_selected_take(self) -> Tuple[Optional[int], Optional[int], Optional[object]]:
        track_id, take_number = self._selected_take_ref()
        if track_id is None or take_number is None:
            return None, None, None
        take = self.recording_controller.session.get_take(int(track_id), int(take_number))
        return int(track_id), int(take_number), take

    def _selected_take_ref(self) -> Tuple[Optional[int], Optional[int]]:
        item = self.take_review_list.currentItem()
        if item is None:
            return None, None
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return None, None
        track_id = data.get("track_id")
        take_number = data.get("take_number")
        if not isinstance(track_id, (int, str)) or not isinstance(take_number, (int, str)):
            return None, None
        try:
            return int(track_id), int(take_number)
        except ValueError:
            return None, None

    def set_selected_take_active(self):
        track_id, take_number = self._selected_take_ref()
        if track_id is None or take_number is None:
            QMessageBox.warning(self, "Take review", "Select a take first.")
            return

        if self.recording_controller.set_active_take(int(track_id), int(take_number)):
            self._sync_take_clips_for_track(int(track_id))
            self._set_active_take_clip_metadata(int(track_id), int(take_number))
            self.recording_controller.session.save_session_metadata()
            self.refresh_take_review_list()
            self.refresh_timeline()
            self.update_status(f"Set take {take_number} active on track {track_id}")
        else:
            QMessageBox.warning(self, "Take review", "Could not set selected take active.")

    def audition_selected_take(self, *_args):
        track_id, take_number = self._selected_take_ref()
        if track_id is None or take_number is None:
            QMessageBox.warning(self, "Take review", "Select a take first.")
            return

        loop_mode = bool(self.take_loop_combo.currentData())
        ok, message = self.recording_controller.audition_take(int(track_id), int(take_number), loop=loop_mode)
        if ok:
            self.update_status(message)
        else:
            QMessageBox.warning(self, "Take audition", message)

    def audition_active_take(self):
        track_id = self.take_track_combo.currentData()
        if track_id is None:
            QMessageBox.warning(self, "Take audition", "Select a track first.")
            return

        active_take = self.recording_controller.session.get_active_takes().get(int(track_id))
        if active_take is None:
            QMessageBox.warning(self, "Take audition", "No active take found for this track.")
            return

        loop_mode = bool(self.take_loop_combo.currentData())
        ok, message = self.recording_controller.audition_take(int(track_id), int(active_take.take_number), loop=loop_mode)
        if ok:
            self.update_status(message)
        else:
            QMessageBox.warning(self, "Take audition", message)

    def stop_take_audition(self):
        was_active = self.recording_controller.stop_audition()
        if was_active:
            self.update_status("Audition stopped")
        else:
            self.update_status("No active audition to stop")

    def delete_selected_take(self):
        track_id, take_number = self._selected_take_ref()
        if track_id is None or take_number is None:
            QMessageBox.warning(self, "Take review", "Select a take first.")
            return

        confirm = QMessageBox.question(
            self,
            "Delete take",
            f"Delete take {take_number} from track {track_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        if self.recording_controller.session.delete_take(int(track_id), int(take_number)):
            self.current_project.clips = [
                clip for clip in self.current_project.clips
                if clip is not self._find_take_clip(int(track_id), int(take_number))
            ]
            active_take = self.recording_controller.session.get_active_takes().get(int(track_id))
            if active_take is not None:
                self._set_active_take_clip_metadata(int(track_id), int(active_take.take_number))
            self.recording_controller.session.save_session_metadata()
            self.refresh_take_review_list()
            self.refresh_timeline()
            self.update_status(f"Deleted take {take_number} from track {track_id}")
        else:
            QMessageBox.warning(self, "Take review", "Could not delete selected take.")

    def toggle_selected_take_keeper(self):
        track_id, take_number, take = self._get_selected_take()
        if take is None or track_id is None or take_number is None:
            QMessageBox.warning(self, "Take review", "Select a take first.")
            return

        new_value = not bool(getattr(take, "is_keeper", False))
        if not self.recording_controller.session.set_take_keeper(track_id, take_number, new_value):
            QMessageBox.warning(self, "Take review", "Could not update keeper tag.")
            return

        self._sync_take_clips_for_track(track_id)
        self.recording_controller.session.save_session_metadata()
        self.refresh_take_review_list()
        self.refresh_timeline()
        self.update_status(f"Take {take_number} keeper set to {new_value}")

    def toggle_selected_take_muted(self):
        track_id, take_number, take = self._get_selected_take()
        if take is None or track_id is None or take_number is None:
            QMessageBox.warning(self, "Take review", "Select a take first.")
            return

        new_value = not bool(getattr(take, "is_muted", False))
        if not self.recording_controller.session.set_take_muted(track_id, take_number, new_value):
            QMessageBox.warning(self, "Take review", "Could not update muted tag.")
            return

        self._sync_take_clips_for_track(track_id)
        self.recording_controller.session.save_session_metadata()
        self.refresh_take_review_list()
        self.refresh_timeline()
        self.update_status(f"Take {take_number} muted set to {new_value}")

    def rate_selected_take(self, delta: int):
        track_id, take_number, take = self._get_selected_take()
        if take is None or track_id is None or take_number is None:
            QMessageBox.warning(self, "Take review", "Select a take first.")
            return

        current_rating = int(getattr(take, "rating", 0))
        new_rating = max(0, min(5, current_rating + int(delta)))
        if not self.recording_controller.session.set_take_rating(track_id, take_number, new_rating):
            QMessageBox.warning(self, "Take review", "Could not update take rating.")
            return

        self._sync_take_clips_for_track(track_id)
        self.recording_controller.session.save_session_metadata()
        self.refresh_take_review_list()
        self.refresh_timeline()
        self.update_status(f"Take {take_number} rating set to {new_rating}")

    def use_best_take_for_selected_track(self):
        track_id = self.take_track_combo.currentData()
        if track_id is None:
            QMessageBox.warning(self, "Take review", "Select a track first.")
            return

        takes = self.recording_controller.get_track_takes(int(track_id))
        if not takes:
            QMessageBox.warning(self, "Take review", "No takes recorded for this track.")
            return

        def score(take) -> tuple:
            keeper_rank = 0 if bool(getattr(take, "is_keeper", False)) else 1
            clip_events = int(getattr(take, "clip_events", 0))
            rating_rank = -int(getattr(take, "rating", 0))
            take_rank = -int(getattr(take, "take_number", 0))
            return (keeper_rank, clip_events, rating_rank, take_rank)

        best_take = sorted(takes, key=score)[0]
        if self.recording_controller.set_active_take(int(track_id), int(best_take.take_number)):
            self._sync_take_clips_for_track(int(track_id))
            self._set_active_take_clip_metadata(int(track_id), int(best_take.take_number))
            self.recording_controller.session.save_session_metadata()
            self.refresh_take_review_list()
            self.refresh_timeline()
            self.update_status(
                f"Best take selected for track {track_id}: take {best_take.take_number} "
                f"(keeper={bool(getattr(best_take, 'is_keeper', False))}, clip_events={int(getattr(best_take, 'clip_events', 0))})"
            )
        else:
            QMessageBox.warning(self, "Take review", "Could not activate best take.")

    def apply_selected_take_note_template(self, template_name: str):
        track_id, take_number, take = self._get_selected_take()
        if take is None or track_id is None or take_number is None:
            QMessageBox.warning(self, "Take review", "Select a take first.")
            return

        if not self.recording_controller.session.apply_take_note_template(track_id, take_number, template_name):
            QMessageBox.warning(self, "Take review", "Could not apply note template.")
            return

        self.recording_controller.session.save_session_metadata()
        self.refresh_take_review_list()
        self.update_status(f"Applied '{template_name}' note template to take {take_number} on track {track_id}")

    def _parse_comp_selection_ms(self) -> Optional[Tuple[int, int]]:
        start_text = self.comp_start_sec_input.text().strip()
        end_text = self.comp_end_sec_input.text().strip()
        if not start_text or not end_text:
            QMessageBox.warning(self, "Comping", "Enter both start and end seconds.")
            return None

        try:
            start_sec = float(start_text)
            end_sec = float(end_text)
        except ValueError:
            QMessageBox.warning(self, "Comping", "Comp range values must be numeric.")
            return None

        if start_sec < 0.0 or end_sec <= start_sec:
            QMessageBox.warning(self, "Comping", "Comp range must be positive and end > start.")
            return None

        return int(round(start_sec * 1000.0)), int(round(end_sec * 1000.0))

    def on_timeline_comp_range_selected(self, track_id: int, start_ms: int, end_ms: int) -> None:
        self.comp_start_sec_input.setText(f"{max(0.0, start_ms / 1000.0):.3f}")
        self.comp_end_sec_input.setText(f"{max(0.0, end_ms / 1000.0):.3f}")
        combo_index = self.take_track_combo.findData(int(track_id))
        if combo_index >= 0:
            self.take_track_combo.setCurrentIndex(combo_index)
        self.update_status(
            f"Comp range selected from timeline: track {track_id}, {start_ms}ms to {end_ms}ms"
        )

    def create_comp_region_from_selection(self):
        track_id, take_number = self._selected_take_ref()
        if track_id is None or take_number is None:
            QMessageBox.warning(self, "Comping", "Select a source take first.")
            return

        parsed = self._parse_comp_selection_ms()
        if parsed is None:
            return
        start_ms, end_ms = parsed

        region = self.recording_controller.session.create_comp_region(int(track_id), int(start_ms), int(end_ms), int(take_number))
        if region is None:
            QMessageBox.warning(self, "Comping", "Could not create comp region for this take/range.")
            return

        self._sync_take_clips_for_track(int(track_id))
        self.recording_controller.session.save_session_metadata()
        self._capture_recovery_snapshot("comp_region_created", interrupted=True)
        self.refresh_timeline()
        self.update_status(
            f"Comp region {region.region_id} created on track {track_id} ({start_ms}ms-{end_ms}ms) using take {take_number}"
        )

    def assign_selected_take_to_comp_region(self):
        track_id, take_number = self._selected_take_ref()
        if track_id is None or take_number is None:
            QMessageBox.warning(self, "Comping", "Select a take first.")
            return

        parsed = self._parse_comp_selection_ms()
        if parsed is None:
            return
        start_ms, end_ms = parsed

        region = self._find_comp_region_for_range(int(track_id), int(start_ms), int(end_ms))
        if region is None:
            QMessageBox.warning(self, "Comping", "No comp region found for this exact range. Create it first.")
            return

        ok = self.recording_controller.session.assign_comp_region_take(int(track_id), int(region.region_id), int(take_number))
        if not ok:
            QMessageBox.warning(self, "Comping", "Could not assign selected take to comp region.")
            return

        self._sync_take_clips_for_track(int(track_id))
        self.recording_controller.session.save_session_metadata()
        self._capture_recovery_snapshot("comp_region_assigned", interrupted=True)
        self.refresh_timeline()
        self.update_status(f"Comp region {region.region_id} now uses take {take_number}")

    def clear_comp_region_from_selection(self):
        track_id = self.take_track_combo.currentData()
        if track_id is None:
            QMessageBox.warning(self, "Comping", "Select a track first.")
            return

        parsed = self._parse_comp_selection_ms()
        if parsed is None:
            return
        start_ms, end_ms = parsed

        region = self._find_comp_region_for_range(int(track_id), int(start_ms), int(end_ms))
        if region is None:
            QMessageBox.warning(self, "Comping", "No comp region found for this exact range.")
            return

        if not self.recording_controller.session.clear_comp_region(int(track_id), int(region.region_id)):
            QMessageBox.warning(self, "Comping", "Could not clear comp region.")
            return

        self._sync_take_clips_for_track(int(track_id))
        self.recording_controller.session.save_session_metadata()
        self._capture_recovery_snapshot("comp_region_cleared", interrupted=True)
        self.refresh_timeline()
        self.update_status(f"Comp region {region.region_id} cleared")

    def _build_recovery_payload(self) -> Dict[str, object]:
        status = self.recording_controller.get_status_snapshot()
        payload: Dict[str, object] = {
            "session": self.recording_controller.session.export_snapshot_payload(),
            "transport": {
                "tempo_bpm": int(status.current_tempo_bpm),
                "time_signature": str(status.time_signature),
                "count_in_bars": int(self.recording_controller.metronome.config.count_in_bars),
                "punch_enabled": bool(self.recording_controller.punch_enabled),
                "punch_in_samples": int(self.recording_controller.punch_in_samples),
                "punch_out_samples": self.recording_controller.punch_out_samples,
                "loop_enabled": bool(self.recording_controller.loop_enabled),
                "loop_start_samples": int(self.recording_controller.loop_start_samples),
                "loop_end_samples": self.recording_controller.loop_end_samples,
                "pre_roll_samples": int(self.recording_controller.pre_roll_samples),
                "post_roll_samples": int(self.recording_controller.post_roll_samples),
            },
            "selected_devices": {
                "input": self.selected_input_device_id,
                "output": self.selected_output_device_id,
            },
        }
        return payload

    def _capture_recovery_snapshot(self, reason: str, interrupted: bool = True) -> None:
        payload = self._build_recovery_payload()
        self.recovery_manager.write_snapshot(
            session_id=self.recording_controller.session.session_id,
            project_name=self.current_project.name,
            payload=payload,
            reason=reason,
            interrupted=interrupted,
        )
        self.refresh_recovery_history()

    def _clear_recovery_snapshot(self) -> None:
        self.recovery_manager.clear_snapshot(self.recording_controller.session.session_id)
        self.refresh_recovery_history()

    def _restore_from_snapshot(self, snapshot: Dict[str, object]) -> bool:
        payload = snapshot.get("payload")
        if not isinstance(payload, dict):
            return False

        session_payload = payload.get("session")
        if not isinstance(session_payload, dict):
            return False

        if not self.recording_controller.session.restore_from_snapshot_payload(session_payload):
            return False

        transport = payload.get("transport")
        if isinstance(transport, dict):
            self.recording_controller.set_tempo(int(transport.get("tempo_bpm", self.recording_controller.status.current_tempo_bpm)))
            time_sig_text = str(transport.get("time_signature", self.recording_controller.status.time_signature))
            if "/" in time_sig_text:
                numerator_text, denominator_text = time_sig_text.split("/", 1)
                try:
                    self.recording_controller.set_time_signature(int(numerator_text), int(denominator_text))
                except ValueError:
                    pass

            self.recording_controller.set_count_in_bars(int(transport.get("count_in_bars", self.recording_controller.metronome.config.count_in_bars)))
            self.recording_controller.set_punch_enabled(bool(transport.get("punch_enabled", False)))
            self.recording_controller.set_loop_enabled(bool(transport.get("loop_enabled", False)))

            punch_in = int(transport.get("punch_in_samples", 0))
            punch_out = transport.get("punch_out_samples")
            self.recording_controller.set_punch_range_samples(punch_in, None if punch_out is None else int(punch_out))

            loop_start = int(transport.get("loop_start_samples", 0))
            loop_end = transport.get("loop_end_samples")
            if loop_end is not None:
                self.recording_controller.set_loop_range_samples(loop_start, int(loop_end))

            pre_roll = int(transport.get("pre_roll_samples", 0))
            post_roll = int(transport.get("post_roll_samples", 0))
            self.recording_controller.set_pre_post_roll_samples(pre_roll, post_roll)

        for track_id in sorted(self.recording_controller.session.takes.keys()):
            self._sync_take_clips_for_track(int(track_id))

        self.refresh_take_review_list()
        self.sync_recording_controls_from_controller()
        self.refresh_timeline()
        self.refresh_recovery_history()
        return True

    def refresh_recovery_history(self) -> None:
        session_id = self.recording_controller.session.session_id
        items = self.recovery_manager.list_snapshot_history(session_id, limit=20)
        self.recovery_history_combo.blockSignals(True)
        self.recovery_history_combo.clear()
        for path in items:
            self.recovery_history_combo.addItem(path.name, str(path))
        self.recovery_history_combo.blockSignals(False)

    def restore_selected_recovery_snapshot(self) -> None:
        selected_path = self.recovery_history_combo.currentData()
        if not selected_path:
            QMessageBox.warning(self, "Recovery", "No recovery snapshot selected.")
            return

        snapshot = self.recovery_manager.load_snapshot_from_path(Path(str(selected_path)))
        if snapshot is None:
            QMessageBox.warning(self, "Recovery", "Could not load selected recovery snapshot.")
            return

        valid, reason = self.recovery_manager.validate_snapshot(
            snapshot,
            expected_session_id=self.recording_controller.session.session_id,
            expected_project_name=self.current_project.name,
            max_age_hours=24 * 30,
        )
        if not valid:
            QMessageBox.warning(self, "Recovery", f"Selected snapshot is invalid: {reason}")
            return

        confirm = QMessageBox.question(
            self,
            "Restore Recovery Snapshot",
            "Restore selected snapshot history entry into current session state?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        if self._restore_from_snapshot(snapshot):
            self.update_status("Recovery snapshot restored from history")
        else:
            QMessageBox.warning(self, "Recovery", "Failed to restore selected recovery snapshot.")

    def _prompt_recovery_for_current_session(self) -> None:
        session_id = self.recording_controller.session.session_id
        snapshot = self.recovery_manager.load_snapshot(session_id)
        if snapshot is None:
            return

        is_valid, reason = self.recovery_manager.validate_snapshot(
            snapshot,
            expected_session_id=session_id,
            expected_project_name=self.current_project.name,
            max_age_hours=24,
        )
        if not is_valid:
            self.recovery_manager.clear_snapshot(session_id)
            self.update_status(f"Recovery snapshot discarded: {reason}")
            return

        choice = QMessageBox.question(
            self,
            "Interrupted Recording Detected",
            "Echo Pro found an interrupted recording snapshot for this session.\n\n"
            "Restore recording state and comp metadata now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if choice == QMessageBox.StandardButton.Yes:
            if self._restore_from_snapshot(snapshot):
                self.update_status("Recovered interrupted recording session state")
            else:
                QMessageBox.warning(self, "Recovery", "Recovery snapshot could not be restored.")
            self.recovery_manager.clear_snapshot(session_id)
            return

        self.recovery_manager.clear_snapshot(session_id)
        self.update_status("Recovery snapshot discarded by user")

    def get_selected_track_index(self):
        row = self.track_list.currentRow()
        if 0 <= row < len(self.current_project.tracks):
            return row
        return None

    def rename_selected_track(self):
        track_index = self.get_selected_track_index()
        if track_index is None:
            QMessageBox.warning(self, "Track selection", "Select a track first.")
            return

        new_name = self.track_name_input.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Input error", "Track name cannot be empty.")
            return

        if self.current_project.tracks[track_index].name == new_name:
            return

        self._mark_project_edit(f"Rename track {track_index + 1}")

        self.current_project.tracks[track_index].name = new_name
        self.sync_project_tracks_to_recording_engine()
        self._build_recording_meters()
        self.refresh_track_list()
        self.refresh_timeline()
        self.update_status(f"Renamed track {track_index} to {new_name}")

    def move_selected_track(self, delta: int):
        track_index = self.get_selected_track_index()
        if track_index is None:
            QMessageBox.warning(self, "Track selection", "Select a track first.")
            return

        target_index = track_index + delta
        if target_index < 0 or target_index >= len(self.current_project.tracks):
            return

        self._mark_project_edit(f"Move track {track_index + 1}")

        tracks = self.current_project.tracks
        tracks[track_index], tracks[target_index] = tracks[target_index], tracks[track_index]

        for clip in self.current_project.clips:
            if clip.track_index == track_index:
                clip.track_index = target_index
            elif clip.track_index == target_index:
                clip.track_index = track_index

        updated_armed = set()
        for armed_track in self.recording_controller.armed_tracks:
            if armed_track == track_index:
                updated_armed.add(target_index)
            elif armed_track == target_index:
                updated_armed.add(track_index)
            else:
                updated_armed.add(armed_track)
        self.recording_controller.armed_tracks = updated_armed
        self.recording_controller.status.active_track_ids = sorted(updated_armed)

        self.selected_track_index = target_index
        self.sync_project_tracks_to_recording_engine()
        self._build_recording_meters()
        self.refresh_track_list()
        self.refresh_timeline()
        self.update_recording_status_label()
        self.update_status(f"Moved track to position {target_index}")

    def delete_selected_track(self):
        track_index = self.get_selected_track_index()
        if track_index is None:
            QMessageBox.warning(self, "Track selection", "Select a track first.")
            return

        track = self.current_project.tracks[track_index]
        clips_on_track = [clip for clip in self.current_project.clips if clip.track_index == track_index]
        clip_count = len(clips_on_track)

        confirm = QMessageBox.question(
            self,
            "Delete track",
            f"Delete track '{track.name}' and {clip_count} clip(s) on it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._mark_project_edit(f"Delete track {track.name}")

        self.current_project.tracks.pop(track_index)
        self.current_project.clips = [clip for clip in self.current_project.clips if clip.track_index != track_index]

        for clip in self.current_project.clips:
            if clip.track_index > track_index:
                clip.track_index -= 1

        updated_armed = set()
        for armed_track in self.recording_controller.armed_tracks:
            if armed_track == track_index:
                continue
            if armed_track > track_index:
                updated_armed.add(armed_track - 1)
            else:
                updated_armed.add(armed_track)
        self.recording_controller.armed_tracks = updated_armed
        self.recording_controller.status.active_track_ids = sorted(updated_armed)
        self.recording_controller.status.is_armed = bool(updated_armed)

        if self.selected_track_index is not None and self.selected_track_index >= len(self.current_project.tracks):
            self.selected_track_index = len(self.current_project.tracks) - 1 if self.current_project.tracks else None

        self.sync_project_tracks_to_recording_engine()
        self._build_recording_meters()
        self.refresh_track_list()
        self.refresh_timeline()
        self.update_recording_status_label()
        self.update_status(f"Deleted track {track.name}")

    def toggle_selected_track_mute(self):
        track_index = self.get_selected_track_index()
        if track_index is None:
            QMessageBox.warning(self, "Track selection", "Select a track first.")
            return

        track = self.current_project.tracks[track_index]
        track.muted = not track.muted
        self.sync_project_tracks_to_recording_engine()
        self.refresh_track_list()
        self.update_status(f"Track {track_index} mute set to {track.muted}")

    def toggle_selected_track_solo(self):
        track_index = self.get_selected_track_index()
        if track_index is None:
            QMessageBox.warning(self, "Track selection", "Select a track first.")
            return

        track = self.current_project.tracks[track_index]
        track.soloed = not track.soloed
        self.sync_project_tracks_to_recording_engine()
        self.refresh_track_list()
        self.update_status(f"Track {track_index} solo set to {track.soloed}")

    def toggle_arm_selected_track(self):
        track_index = self.get_selected_track_index()
        if track_index is None:
            QMessageBox.warning(self, "Track selection", "Select a track first.")
            return

        if track_index in self.recording_controller.armed_tracks:
            self.recording_controller.disarm_track(track_index)
            self.update_status(f"Disarmed track {track_index}")
        elif self.recording_controller.arm_track(track_index):
            self.update_status(f"Armed track {track_index}")
        else:
            QMessageBox.warning(self, "Recording", self.recording_controller.status.last_error or "Could not arm track.")

        self.refresh_track_list()
        self.update_recording_status_label()

    def update_recording_status_label(self):
        status = self.recording_controller.get_status_snapshot()
        state = "count-in" if status.count_in_active else "recording" if status.is_recording else "armed" if status.is_armed else "idle"
        armed_text = ", ".join(str(track_id) for track_id in status.active_track_ids) or "none"
        count_in_bars = self.recording_controller.metronome.config.count_in_bars
        if self.recording_controller.punch_enabled:
            punch_in = self.recording_controller.samples_to_bars(self.recording_controller.punch_in_samples)
            if self.recording_controller.punch_out_samples is None:
                punch_text = f"on @ {punch_in:.2f} bars -> manual stop"
            else:
                punch_out = self.recording_controller.samples_to_bars(self.recording_controller.punch_out_samples)
                punch_text = f"on @ {punch_in:.2f} to {punch_out:.2f} bars"
        else:
            punch_text = "off"

        if self.recording_controller.loop_enabled:
            loop_start = self.recording_controller.samples_to_bars(self.recording_controller.loop_start_samples)
            if self.recording_controller.loop_end_samples is None:
                loop_text = "on"
            else:
                loop_end = self.recording_controller.samples_to_bars(self.recording_controller.loop_end_samples)
                loop_text = f"on @ {loop_start:.2f} to {loop_end:.2f} bars"
            if self.recording_controller.loop_cycle_index > 0:
                loop_text += f" (cycle {self.recording_controller.loop_cycle_index})"
        else:
            loop_text = "off"

        roll_text = f"{status.pre_roll_bars:.2f}/{status.post_roll_bars:.2f} bars"
        monitor_text = f"{'on' if status.monitoring_enabled else 'off'} @ {int(status.monitor_gain_percent)}%"
        self.recording_status_label.setText(
            f"Recording: {state} | Tempo: {status.current_tempo_bpm} BPM | Time Sig: {status.time_signature} | Count-In: {count_in_bars} bar(s) | Roll(pre/post): {roll_text} | Punch: {punch_text} | Loop: {loop_text} | Monitor: {monitor_text} | Armed: {armed_text}"
        )

    def sync_recording_controls_from_controller(self):
        self.record_tempo_input.setText(str(self.recording_controller.status.current_tempo_bpm))
        self.record_time_sig_input.setText(self.recording_controller.status.time_signature)
        self.record_count_in_input.setText(str(self.recording_controller.metronome.config.count_in_bars))
        self.pre_roll_bar_input.setText(f"{self.recording_controller.samples_to_bars(self.recording_controller.pre_roll_samples):.2f}")
        self.post_roll_bar_input.setText(f"{self.recording_controller.samples_to_bars(self.recording_controller.post_roll_samples):.2f}")

        punch_index = self.punch_mode_combo.findData(bool(self.recording_controller.punch_enabled))
        if punch_index >= 0:
            self.punch_mode_combo.setCurrentIndex(punch_index)
        punch_in_bars = self.recording_controller.samples_to_bars(self.recording_controller.punch_in_samples)
        self.punch_in_bar_input.setText(f"{punch_in_bars:.2f}")
        if self.recording_controller.punch_out_samples is None:
            self.punch_out_bar_input.setText("")
        else:
            punch_out_bars = self.recording_controller.samples_to_bars(self.recording_controller.punch_out_samples)
            self.punch_out_bar_input.setText(f"{punch_out_bars:.2f}")

        loop_index = self.loop_mode_combo.findData(bool(self.recording_controller.loop_enabled))
        if loop_index >= 0:
            self.loop_mode_combo.setCurrentIndex(loop_index)
        loop_start_bars = self.recording_controller.samples_to_bars(self.recording_controller.loop_start_samples)
        self.loop_start_bar_input.setText(f"{loop_start_bars:.2f}")
        if self.recording_controller.loop_end_samples is None:
            self.loop_end_bar_input.setText("")
        else:
            loop_end_bars = self.recording_controller.samples_to_bars(self.recording_controller.loop_end_samples)
            self.loop_end_bar_input.setText(f"{loop_end_bars:.2f}")

        mixer_layout = getattr(self, "main_mixer_view", None)
        if mixer_layout is not None and hasattr(mixer_layout, "_sync_mixer_transport_controls_from_window"):
            mixer_layout._sync_mixer_transport_controls_from_window()

    def refresh_recording_meters(self):
        levels = self.recording_controller.get_meter_levels()
        for track_id, meter in self.recording_meters.items():
            track_levels = levels.get(track_id)
            if track_levels is not None:
                meter.update_levels(
                    track_levels["current_db"],
                    track_levels["peak_db"],
                    clipping=track_levels.get("clipping", 0.0) >= 0.5,
                )

        self.recording_diagnostics_widget.update_diagnostics(self.recording_controller.get_transport_diagnostics())

        if self.recording_controller.consume_auto_stop_event():
            status_after_stop = self.recording_controller.get_status_snapshot()
            self.recording_controller.stop_stream()
            for track_id in sorted(self.recording_controller.session.takes.keys()):
                self._sync_take_clips_for_track(int(track_id))
            self._clear_recovery_snapshot()
            self.refresh_timeline()
            self.refresh_take_review_list()
            self._set_recording_transport_button_state(can_record=True, can_stop=False)
            self._sync_metronome_button_state(False)
            self.update_status(
                f"Recording boundary reached: transport auto-stopped @ sample {status_after_stop.last_auto_stop_sample}"
            )

        self.update_recording_status_label()

    def refresh_audio_device_selectors(self):
        current_input = self.input_device_combo.currentData()
        current_output = self.output_device_combo.currentData()

        device_manager.refresh_devices()
        input_devices = device_manager.get_input_devices()
        output_devices = device_manager.get_output_devices()

        self.input_device_combo.clear()
        self.output_device_combo.clear()

        for device in input_devices:
            label = f"{device.device_id}: {device.name}"
            if device.is_default_input:
                label += " [Default]"
            self.input_device_combo.addItem(label, device.device_id)

        for device in output_devices:
            label = f"{device.device_id}: {device.name}"
            if device.is_default_output:
                label += " [Default]"
            self.output_device_combo.addItem(label, device.device_id)

        if self.input_device_combo.count() == 0 or self.output_device_combo.count() == 0:
            self.update_status("No usable audio input/output devices detected")
            return

        input_to_select = current_input if current_input is not None else device_manager.selected_input_device
        output_to_select = current_output if current_output is not None else device_manager.selected_output_device

        input_index = self.input_device_combo.findData(input_to_select)
        output_index = self.output_device_combo.findData(output_to_select)

        self.input_device_combo.setCurrentIndex(input_index if input_index >= 0 else 0)
        self.output_device_combo.setCurrentIndex(output_index if output_index >= 0 else 0)

        self.selected_input_device_id = self.input_device_combo.currentData()
        self.selected_output_device_id = self.output_device_combo.currentData()
        if self.selected_input_device_id is not None:
            device_manager.select_input_device(int(self.selected_input_device_id))
        if self.selected_output_device_id is not None:
            device_manager.select_output_device(int(self.selected_output_device_id))

        if hasattr(self, "sample_rate_combo"):
            sample_rate_index = self.sample_rate_combo.findData(int(device_manager.selected_sample_rate))
            if sample_rate_index >= 0:
                self.sample_rate_combo.setCurrentIndex(sample_rate_index)
        self.update_status("Audio device list refreshed")
        self._refresh_status_bar_telemetry()

        mixer_layout = getattr(self, "main_mixer_view", None)
        if mixer_layout is not None and hasattr(mixer_layout, "_sync_mixer_transport_controls_from_window"):
            mixer_layout._sync_mixer_transport_controls_from_window()

    def test_audio_devices(self):
        input_id = self.input_device_combo.currentData()
        output_id = self.output_device_combo.currentData()

        if input_id is None or output_id is None:
            QMessageBox.warning(self, "Audio device test", "Select both input and output devices first.")
            return

        if not device_manager.select_input_device(int(input_id)):
            QMessageBox.warning(self, "Audio device test", "Selected input device is not usable.")
            return

        if not device_manager.select_output_device(int(output_id)):
            QMessageBox.warning(self, "Audio device test", "Selected output device is not usable.")
            return

        preflight = device_manager.get_preflight_summary(required_input_channels=2, required_output_channels=2)
        ok, message = device_manager.test_device_configuration()
        details = device_manager.format_preflight_summary(preflight)

        if ok:
            QMessageBox.information(
                self,
                "Audio Device Test Passed",
                f"Result: {message}\n\n{details}",
            )
            self.update_status(
                f"Device test passed ({float(preflight.get('total_latency_ms', 0.0)):.1f} ms round trip)"
            )
        else:
            QMessageBox.critical(
                self,
                "Audio Device Test Failed",
                f"Result: {message}\n\n{details}",
            )
            self.update_status("Device test failed")

    def _on_sample_rate_changed(self, *_args) -> None:
        if not hasattr(self, "sample_rate_combo"):
            return
        selected_sample_rate = self.sample_rate_combo.currentData()
        if isinstance(selected_sample_rate, int) and selected_sample_rate > 0:
            device_manager.set_sample_rate(int(selected_sample_rate))
            self._refresh_status_bar_telemetry()

    def run_validation_checks(self):
        self.update_status("Running validation checks...")
        workspace_root = Path(__file__).resolve().parent
        command = str(workspace_root / "tools" / "dev" / "run_ui_smoke_checks.bat")
        completed = subprocess.run(command, cwd=str(workspace_root), capture_output=True, text=True, shell=True)
        output = (completed.stdout or completed.stderr or "").strip()
        if completed.returncode == 0:
            QMessageBox.information(self, "Validation Checks", output or "UI smoke checks passed.")
            self.update_status("Validation checks complete: UI smoke checks passed")
        else:
            QMessageBox.warning(self, "Validation Checks", output or "UI smoke checks failed.")
            self.update_status(f"Validation checks failed with exit code {completed.returncode}")

    def run_p5b_regression_checks(self):
        self.update_status("Running P5B regression checks...")
        report = run_phase5b_regression_checks()
        summary = format_p5b_regression_summary(report)

        failed_raw = report.get("failed", 0)
        if isinstance(failed_raw, (int, float, str)):
            try:
                failed_count = int(failed_raw)
            except ValueError:
                failed_count = 0
        else:
            failed_count = 0

        passed_raw = report.get("passed", 0)
        if isinstance(passed_raw, (int, float, str)):
            try:
                passed_count = int(passed_raw)
            except ValueError:
                passed_count = 0
        else:
            passed_count = 0

        if failed_count == 0:
            QMessageBox.information(self, "P5B Regression Checks", summary)
        else:
            QMessageBox.warning(self, "P5B Regression Checks", summary)

        self.update_status(f"P5B regression checks complete: {passed_count} passed, {failed_count} failed")

    def arm_recording_track(self):
        try:
            track_index = int(self.record_track_input.text())
        except ValueError:
            QMessageBox.warning(self, "Input error", "Track index must be a number.")
            return

        if self.recording_controller.arm_track(track_index):
            self.update_status(f"Armed recording track {track_index}")
            self.update_recording_status_label()
        else:
            QMessageBox.warning(self, "Input error", self.recording_controller.status.last_error or "Could not arm track.")

    def arm_all_recording_tracks(self):
        self.recording_controller.arm_all_tracks()
        self.update_status("All recording tracks armed")
        self.update_recording_status_label()

    def clear_armed_recording_tracks(self):
        self.recording_controller.clear_armed_tracks()
        self.update_status("Cleared armed recording tracks")
        self.update_recording_status_label()

    def set_recording_tempo(self):
        try:
            tempo = int(self.record_tempo_input.text())
        except ValueError:
            QMessageBox.warning(self, "Input error", "Tempo must be a number.")
            return

        self.recording_controller.set_tempo(tempo)
        self.update_status(f"Recording tempo set to {tempo} BPM")
        self.update_recording_status_label()

    def set_recording_time_signature(self):
        parsed_signature = self._parse_time_signature(self.record_time_sig_input.text(), field_name="Recording time signature")
        if parsed_signature is None:
            return
        numerator_text, denominator_text = parsed_signature.split("/", 1)
        numerator = int(numerator_text)
        denominator = int(denominator_text)

        self.recording_controller.set_time_signature(numerator, denominator)
        self.update_status(f"Recording time signature set to {numerator}/{denominator}")
        self.update_recording_status_label()

    def set_recording_count_in(self):
        try:
            bars = int(self.record_count_in_input.text())
        except ValueError:
            QMessageBox.warning(self, "Input error", "Count-in bars must be a number.")
            return

        if bars < 0:
            QMessageBox.warning(self, "Input error", "Count-in bars cannot be negative.")
            return

        self.recording_controller.set_count_in_bars(bars)
        self.update_status(f"Count-in set to {bars} bar(s)")
        self.update_recording_status_label()

    def set_recording_pre_post_roll(self):
        pre_roll_text = self.pre_roll_bar_input.text().strip()
        post_roll_text = self.post_roll_bar_input.text().strip()

        try:
            pre_roll_bars = float(pre_roll_text) if pre_roll_text else 0.0
        except ValueError:
            QMessageBox.warning(self, "Input error", "Pre-roll value must be a number.")
            return

        try:
            post_roll_bars = float(post_roll_text) if post_roll_text else 0.0
        except ValueError:
            QMessageBox.warning(self, "Input error", "Post-roll value must be a number.")
            return

        if not self.recording_controller.set_pre_post_roll_bars(pre_roll_bars, post_roll_bars):
            QMessageBox.warning(
                self,
                "Pre/Post roll setup",
                self.recording_controller.status.last_error or "Could not apply pre/post-roll settings.",
            )
            return

        self.update_status(f"Pre/Post roll set ({pre_roll_bars:.2f}/{post_roll_bars:.2f} bars)")
        self.update_recording_status_label()

    def on_punch_mode_changed(self, *_args):
        enabled = bool(self.punch_mode_combo.currentData())
        if enabled and bool(self.loop_mode_combo.currentData()):
            self.loop_mode_combo.setCurrentIndex(self.loop_mode_combo.findData(False))
            self.recording_controller.set_loop_enabled(False)
            self.update_status("Loop mode disabled because punch mode was enabled")
        self.recording_controller.set_punch_enabled(enabled)
        self.update_status("Punch mode enabled" if enabled else "Punch mode disabled")
        self.update_recording_status_label()
        mixer_layout = getattr(self, "main_mixer_view", None)
        if mixer_layout is not None and hasattr(mixer_layout, "_sync_mixer_transport_controls_from_window"):
            mixer_layout._sync_mixer_transport_controls_from_window()

    def set_recording_punch_range(self):
        punch_in_text = self.punch_in_bar_input.text().strip()
        punch_out_text = self.punch_out_bar_input.text().strip()

        try:
            punch_in_bars = float(punch_in_text) if punch_in_text else 0.0
        except ValueError:
            QMessageBox.warning(self, "Input error", "Punch-in value must be a number.")
            return

        punch_out_bars = None
        if punch_out_text:
            try:
                punch_out_bars = float(punch_out_text)
            except ValueError:
                QMessageBox.warning(self, "Input error", "Punch-out value must be a number.")
                return

        if not self.recording_controller.set_punch_range_bars(punch_in_bars, punch_out_bars):
            QMessageBox.warning(
                self,
                "Punch setup",
                self.recording_controller.status.last_error or "Could not apply punch range.",
            )
            return

        self.update_status(
            "Punch range set "
            f"({punch_in_bars:.2f} bars to {'manual stop' if punch_out_bars is None else f'{punch_out_bars:.2f} bars'})"
        )
        self.update_recording_status_label()
        mixer_layout = getattr(self, "main_mixer_view", None)
        if mixer_layout is not None and hasattr(mixer_layout, "_sync_mixer_transport_controls_from_window"):
            mixer_layout._sync_mixer_transport_controls_from_window()

    def on_loop_mode_changed(self, *_args):
        enabled = bool(self.loop_mode_combo.currentData())
        if enabled and bool(self.punch_mode_combo.currentData()):
            self.punch_mode_combo.setCurrentIndex(self.punch_mode_combo.findData(False))
            self.recording_controller.set_punch_enabled(False)
            self.update_status("Punch mode disabled because loop mode was enabled")
        self.recording_controller.set_loop_enabled(enabled)
        self.update_status("Loop mode enabled" if enabled else "Loop mode disabled")
        self.update_recording_status_label()
        mixer_layout = getattr(self, "main_mixer_view", None)
        if mixer_layout is not None and hasattr(mixer_layout, "_sync_mixer_transport_controls_from_window"):
            mixer_layout._sync_mixer_transport_controls_from_window()

    def set_recording_loop_range(self):
        loop_start_text = self.loop_start_bar_input.text().strip()
        loop_end_text = self.loop_end_bar_input.text().strip()

        try:
            loop_start_bars = float(loop_start_text) if loop_start_text else 0.0
        except ValueError:
            QMessageBox.warning(self, "Input error", "Loop start value must be a number.")
            return

        if not loop_end_text:
            QMessageBox.warning(self, "Input error", "Loop end value is required.")
            return

        try:
            loop_end_bars = float(loop_end_text)
        except ValueError:
            QMessageBox.warning(self, "Input error", "Loop end value must be a number.")
            return

        if not self.recording_controller.set_loop_range_bars(loop_start_bars, loop_end_bars):
            QMessageBox.warning(
                self,
                "Loop setup",
                self.recording_controller.status.last_error or "Could not apply loop range.",
            )
            return

        self.update_status(f"Loop range set ({loop_start_bars:.2f} to {loop_end_bars:.2f} bars)")
        self.update_recording_status_label()
        mixer_layout = getattr(self, "main_mixer_view", None)
        if mixer_layout is not None and hasattr(mixer_layout, "_sync_mixer_transport_controls_from_window"):
            mixer_layout._sync_mixer_transport_controls_from_window()

    def toggle_metronome(self):
        if self.recording_controller.metronome.is_running:
            self.recording_controller.metronome.stop()
            self._sync_metronome_button_state(False)
            self.update_status("Metronome stopped")
        else:
            self.recording_controller.metronome.start()
            self._sync_metronome_button_state(True)
            self.update_status("Metronome started")
        self.update_recording_status_label()

    def start_recording_session(self):
        if not self.recording_controller.armed_tracks:
            QMessageBox.warning(self, "Recording", "Arm at least one track before recording.")
            return

        self.recording_controller.stop_audition()

        self.recording_controller.session.project_name = self.current_project.name

        selected_input = self.input_device_combo.currentData()
        selected_output = self.output_device_combo.currentData()
        if selected_input is None or selected_output is None:
            QMessageBox.critical(self, "Recording error", "Select valid input and output devices before recording.")
            return

        self.selected_input_device_id = selected_input
        self.selected_output_device_id = selected_output

        if not self.recording_controller.start_stream(input_device=selected_input, output_device=selected_output):
            QMessageBox.critical(
                self,
                "Recording error",
                self.recording_controller.status.last_error or "Could not start the audio stream."
            )
            return

        if not self.recording_controller.start_recording():
            QMessageBox.critical(
                self,
                "Recording error",
                self.recording_controller.status.last_error or "Could not start recording."
            )
            self.recording_controller.stop_stream()
            return

        self._capture_recovery_snapshot("recording_started", interrupted=True)

        self._set_recording_transport_button_state(can_record=False, can_stop=True)
        self.update_status(f"Recording started (Input {selected_input}, Output {selected_output})")
        self.update_recording_status_label()

    def stop_recording_session(self):
        if self.recording_controller.status.is_recording or self.recording_controller.status.count_in_active:
            self.recording_controller.stop_recording(duration_seconds=0.0, level_stats={})
            self.recording_controller.stop_stream()

            for track_id in sorted(self.recording_controller.session.takes.keys()):
                self._sync_take_clips_for_track(int(track_id))
            self._clear_recovery_snapshot()
            self.refresh_timeline()

        self._set_recording_transport_button_state(can_record=True, can_stop=False)
        self._sync_metronome_button_state(False)
        self.refresh_take_review_list()
        self.update_status("Recording stopped")
        self.update_recording_status_label()

    def undo_last_recording_take(self):
        take = self.recording_controller.undo_last_take()
        if take is None:
            if not self.undo_project_edit():
                self.update_status("Nothing to undo")
                return
        else:
            self._sync_take_clips_for_track(int(take.track_id))
            self.refresh_timeline()
            self.update_status(f"Undid take {take.take_number} on track {take.track_id}")
        self.refresh_take_review_list()
        self.update_recording_status_label()

    def redo_last_recording_take(self):
        take = self.recording_controller.redo_last_take()
        if take is None:
            if not self.redo_project_edit():
                self.update_status("Nothing to redo")
                return
        else:
            self._sync_take_clips_for_track(int(take.track_id))
            self.refresh_timeline()
            self.update_status(f"Redid take {take.take_number} on track {take.track_id}")
        self.refresh_take_review_list()
        self.update_recording_status_label()

    def update_status(self, text: str):
        self.status.showMessage(text)
        self._refresh_status_bar_telemetry()

    def _snapshot_project_edit_state(self) -> dict:
        return {
            "project": copy.deepcopy(self.current_project),
            "next_clip_id": int(self.next_clip_id),
            "selected_track_index": self.selected_track_index,
            "project_playhead_ms": int(self.project_playhead_ms),
        }

    def _restore_project_edit_state(self, snapshot: dict) -> None:
        self.current_project = copy.deepcopy(snapshot.get("project", self.current_project))
        self.next_clip_id = int(snapshot.get("next_clip_id", self.next_clip_id))
        self.selected_track_index = snapshot.get("selected_track_index", self.selected_track_index)
        self.project_playhead_ms = int(snapshot.get("project_playhead_ms", self.project_playhead_ms))

        if self.selected_track_index is not None and not (0 <= int(self.selected_track_index) < len(self.current_project.tracks)):
            self.selected_track_index = len(self.current_project.tracks) - 1 if self.current_project.tracks else None

        self.sync_project_tracks_to_recording_engine()
        self._build_recording_meters()
        self.refresh_track_list()
        self.refresh_take_track_selector()
        self.refresh_take_review_list()
        self.refresh_timeline()
        self._update_playback_position_label()

    def _clear_project_history(self) -> None:
        self._project_undo_stack.clear()
        self._project_redo_stack.clear()

    def _push_project_snapshot(self, description: str, snapshot: dict) -> None:
        if self._project_history_suspended:
            return
        self._project_undo_stack.append({
            "description": str(description),
            "snapshot": snapshot,
        })
        if len(self._project_undo_stack) > int(self._project_history_limit):
            self._project_undo_stack = self._project_undo_stack[-int(self._project_history_limit):]
        self._project_redo_stack.clear()

    def _mark_project_edit(self, description: str) -> None:
        self._push_project_snapshot(str(description), self._snapshot_project_edit_state())
        self._refresh_application_state_machine()

    def _selected_timeline_clip(self) -> Optional[Clip]:
        timeline = getattr(self, "timeline", None)
        if timeline is None:
            return None
        selected_clip_id = getattr(timeline, "selected_clip_id", None)
        if selected_clip_id is None:
            return None
        for clip in self.current_project.clips:
            if int(clip.id) == int(selected_clip_id):
                return clip
        return None

    def delete_selected_timeline_clip(self) -> bool:
        clip = self._selected_timeline_clip()
        if clip is None:
            self.update_status("No timeline clip selected")
            return False

        self._mark_project_edit(f"Delete clip {int(clip.id)}")
        self.current_project.clips = [
            existing for existing in self.current_project.clips if int(existing.id) != int(clip.id)
        ]
        if hasattr(self.timeline, "selected_clip_id"):
            self.timeline.selected_clip_id = None
        self.refresh_timeline()
        self.update_status(f"Deleted clip {int(clip.id)}")
        return True

    def split_selected_clip_at_playhead(self) -> bool:
        clip = self._selected_timeline_clip()
        if clip is None:
            self.update_status("Select a timeline clip before splitting")
            return False

        clip_start_ms = int(clip.start_ms)
        clip_end_ms = int(clip.start_ms) + int(clip.length_ms)
        split_ms = int(self.project_playhead_ms)
        if split_ms <= clip_start_ms or split_ms >= clip_end_ms:
            self.update_status("Move the playhead inside the selected clip to split")
            return False

        left_length_ms = int(split_ms - clip_start_ms)
        right_length_ms = int(clip_end_ms - split_ms)
        if left_length_ms < 10 or right_length_ms < 10:
            self.update_status("Split too close to clip boundary")
            return False

        source_path = Path(clip.file_path)
        if not source_path.exists():
            QMessageBox.warning(self, "Split Clip", "Selected clip source file is missing on disk.")
            return False

        try:
            samples, sample_rate = sf.read(str(source_path), dtype="float32", always_2d=True)
            clip_frame_count = max(1, int(round((float(max(1, int(clip.length_ms))) / 1000.0) * float(sample_rate))))
            bounded_clip = samples[:min(samples.shape[0], clip_frame_count), :]
            split_frame = int(round((float(left_length_ms) / 1000.0) * float(sample_rate)))
            split_frame = max(1, min(split_frame, max(1, bounded_clip.shape[0] - 1)))
            right_segment = bounded_clip[split_frame:, :]
            if right_segment.shape[0] <= 0:
                self.update_status("Split failed: right clip would be empty")
                return False

            split_dir = (self._project_save_directory or PROJECTS_DIR) / "split_clips"
            split_dir.mkdir(parents=True, exist_ok=True)
            output_name = f"{source_path.stem}_clip{int(clip.id)}_partB_{int(time.time())}.wav"
            right_path = split_dir / output_name
            sf.write(str(right_path), right_segment, int(sample_rate))
        except Exception as exc:
            QMessageBox.critical(self, "Split Clip", f"Could not split clip:\n{exc}")
            return False

        self._mark_project_edit(f"Split clip {int(clip.id)} at {split_ms / 1000.0:.2f}s")
        clip.length_ms = int(left_length_ms)
        right_metadata = dict(getattr(clip, "metadata", {}) or {})
        base_name = str(right_metadata.get("display_name", "")).strip() or source_path.stem
        right_metadata["display_name"] = f"{base_name} (Part B)"
        right_clip = Clip(
            id=int(self.next_clip_id),
            track_index=int(clip.track_index),
            file_path=str(right_path),
            start_ms=int(split_ms),
            length_ms=int(right_length_ms),
            metadata=right_metadata,
        )
        self.current_project.clips.append(right_clip)
        self.next_clip_id += 1
        if hasattr(self.timeline, "selected_clip_id"):
            self.timeline.selected_clip_id = int(right_clip.id)
        self.refresh_timeline()
        self.update_status(f"Split clip {int(clip.id)} at {split_ms / 1000.0:.2f}s")
        return True

    def undo_project_edit(self) -> bool:
        if not self._project_undo_stack:
            return False
        entry = self._project_undo_stack.pop()
        self._project_redo_stack.append({
            "description": str(entry.get("description", "")),
            "snapshot": self._snapshot_project_edit_state(),
        })
        self._project_history_suspended = True
        try:
            self._restore_project_edit_state(entry["snapshot"])
        finally:
            self._project_history_suspended = False
        self.update_status(f"Undo: {entry.get('description', 'Project edit')}")
        return True

    def redo_project_edit(self) -> bool:
        if not self._project_redo_stack:
            return False
        entry = self._project_redo_stack.pop()
        self._project_undo_stack.append({
            "description": str(entry.get("description", "")),
            "snapshot": self._snapshot_project_edit_state(),
        })
        self._project_history_suspended = True
        try:
            self._restore_project_edit_state(entry["snapshot"])
        finally:
            self._project_history_suspended = False
        self.update_status(f"Redo: {entry.get('description', 'Project edit')}")
        return True

    def toggle_mixer_sidebar(self) -> None:
        mixer_layout = getattr(self, "main_mixer_view", None)
        callback = getattr(mixer_layout, "toggle_sidebar", None)
        if callable(callback):
            callback()
            self.update_status("Toggled Mixer sidebar")
            return
        self.update_status("Mixer sidebar toggle is unavailable")

    def open_app_settings_dialog(self) -> None:
        if hasattr(self, "tabs"):
            for index in range(self.tabs.count()):
                if self.tabs.tabText(index) == "Recording":
                    self.tabs.setCurrentIndex(index)
                    break
        message = (
            "Global settings currently live in the Recording tab.\n\n"
            "Use Audio Devices for input/output routing, sample rate selection, and device tests."
        )
        QMessageBox.information(self, "Settings", message)
        self.update_status("Opened settings (Recording tab)")

    def export_project_mix_dialog(self) -> None:
        if not self.current_project.clips:
            QMessageBox.information(self, "Export Mix", "Add at least one clip before exporting a mix.")
            return

        default_name = f"{self.current_project.name or 'Untitled'}_mix.wav"
        default_path = PROJECTS_DIR / default_name
        target_path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Project Mix",
            str(default_path),
            "WAV Files (*.wav);;FLAC Files (*.flac);;All Files (*)",
        )
        if not target_path_str:
            return

        target_path = Path(target_path_str)
        try:
            mix = mix_project_to_segment(self.current_project)
            if mix.shape[0] == 0:
                QMessageBox.warning(self, "Export Mix", "The rendered mix is empty.")
                return
            target_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(target_path), mix, TARGET_SAMPLE_RATE)
        except Exception as exc:
            QMessageBox.critical(self, "Export Mix", f"Failed to export mix:\n{exc}")
            return

        self.update_status(f"Exported mix to {target_path.name}")

    def set_master_eq_enabled(self, enabled: bool) -> None:
        metadata = dict(getattr(self.current_project, "metadata", {}) or {})
        metadata["master_eq_enabled"] = bool(enabled)
        mastering_state = dict(metadata.get("mastering_chain", {}) or {})
        mastering_state["eq_bypassed"] = not bool(enabled)
        metadata["mastering_chain"] = mastering_state
        self.current_project.metadata = metadata
        self.update_status(f"Master EQ {'enabled' if enabled else 'bypassed'}")

    def set_master_limiter_threshold_db(self, threshold_db: int) -> None:
        metadata = dict(getattr(self.current_project, "metadata", {}) or {})
        limiter_db = max(-24, min(0, int(threshold_db)))
        metadata["master_limiter_threshold_db"] = limiter_db
        mastering_state = dict(metadata.get("mastering_chain", {}) or {})
        mastering_state["limiter_threshold_db"] = limiter_db
        metadata["mastering_chain"] = mastering_state
        self.current_project.metadata = metadata

    def _mastering_preset_to_target_db(self, preset_name: str) -> float:
        preset = str(preset_name or "").strip()
        mapping = {
            "Spotify -14": -14.0,
            "YouTube -16": -16.0,
            "EBU R128 -23": -23.0,
            "ATSC -24": -24.0,
        }
        return float(mapping.get(preset, float(self._master_lufs_target_db)))

    def _mastering_chain_defaults(self) -> dict:
        return {
            "input_trim_db": 0,
            "input_trim_bypassed": False,
            "eq_bypassed": False,
            "eq_low_gain_db": 0.0,
            "eq_low_mid_gain_db": 0.0,
            "eq_high_mid_gain_db": 0.0,
            "eq_high_gain_db": 0.0,
            "compressor_bypassed": False,
            "compressor_threshold_db": -12,
            "compressor_ratio": 2.0,
            "compressor_attack_ms": 10,
            "compressor_release_ms": 120,
            "compressor_knee_db": 4.0,
            "compressor_makeup_db": 0,
            "widener_bypassed": False,
            "widener_width_pct": 100,
            "limiter_bypassed": False,
            "limiter_threshold_db": -3,
            "limiter_ceiling_db": -1,
            "limiter_release_ms": 80,
            "output_bypassed": False,
            "lufs_target_preset": "Spotify -14",
            "lufs_target_db": -14.0,
        }

    def _mastering_chain_state(self) -> dict:
        metadata = dict(getattr(self.current_project, "metadata", {}) or {})
        state = self._mastering_chain_defaults()
        stored = metadata.get("mastering_chain")
        if isinstance(stored, dict):
            state.update(stored)
        state["lufs_target_db"] = self._mastering_preset_to_target_db(str(state.get("lufs_target_preset", "Spotify -14")))
        return state

    def _save_mastering_chain_state(self, state: dict) -> None:
        metadata = dict(getattr(self.current_project, "metadata", {}) or {})
        metadata["mastering_chain"] = dict(state)
        metadata["master_eq_enabled"] = not bool(state.get("eq_bypassed", False))
        metadata["master_limiter_threshold_db"] = int(state.get("limiter_threshold_db", -3))
        self.current_project.metadata = metadata
        self._refresh_status_bar_telemetry()

    def open_master_effects_chain(self) -> None:
        if hasattr(self, "tabs"):
            self._switch_to_tab("Mastering")
            return
        self.open_app_settings_dialog()
        QMessageBox.information(
            self,
            "Master Effects Chain",
            "Master effects are applied at export/playback render time in this build.\n"
            "Track-level FX and fades are configured per channel strip via FX/EQ buttons.",
        )

    def _update_playback_position_label(self) -> None:
        self.playback_position_label.setText(f"Playhead {self.project_playhead_ms / 1000.0:.2f}s")

    def _set_project_playhead_ms(self, value_ms: int, *, sync_controller: bool = True) -> None:
        project_end_ms = project_duration_ms(self.current_project)
        self.project_playhead_ms = max(0, min(int(value_ms), project_end_ms))
        self.timeline.set_playhead_ms(self.project_playhead_ms)
        if sync_controller:
            timeline_controller = getattr(self, "timeline_controller", None)
            if timeline_controller is not None:
                timeline_controller.set_playhead(self.project_playhead_ms)
        self._update_playback_position_label()

    def _timeline_zoom_factor(self) -> float:
        timeline_controller = getattr(self, "timeline_controller", None)
        if timeline_controller is not None:
            return float(timeline_controller.get_zoom_factor())
        if hasattr(self, "timeline") and hasattr(self.timeline, "get_zoom_factor"):
            return float(self.timeline.get_zoom_factor())
        return 1.0

    def _update_timeline_zoom_readout(self) -> None:
        if not hasattr(self, "timeline_zoom_label"):
            return
        zoom_percent = int(round(self._timeline_zoom_factor() * 100.0))
        self.timeline_zoom_label.setText(f"Zoom {zoom_percent}%")

    def _set_timeline_zoom_factor(self, zoom_factor: float, *, anchor_view_x: Optional[int] = None) -> None:
        if not hasattr(self, "timeline") or not hasattr(self, "timeline_scroll"):
            return

        current_zoom = self._timeline_zoom_factor()
        next_zoom = max(0.0625, min(64.0, float(zoom_factor)))
        if abs(next_zoom - current_zoom) <= 1e-9:
            self._update_timeline_zoom_readout()
            return

        scroll_bar = self.timeline_scroll.horizontalScrollBar()
        viewport_width = int(self.timeline_scroll.viewport().width())
        view_x = int(anchor_view_x) if anchor_view_x is not None else int(viewport_width / 2)
        view_x = max(0, min(viewport_width, view_x))
        absolute_before_px = int(scroll_bar.value()) + view_x
        normalized_anchor = float(absolute_before_px) / max(1e-9, current_zoom)

        timeline_controller = getattr(self, "timeline_controller", None)
        if timeline_controller is not None:
            timeline_controller.set_zoom_factor(next_zoom)
        else:
            self.timeline.set_zoom_factor(next_zoom)

        absolute_after_px = int(round(normalized_anchor * next_zoom))
        new_scroll_value = max(scroll_bar.minimum(), min(scroll_bar.maximum(), absolute_after_px - view_x))
        scroll_bar.setValue(new_scroll_value)
        self._update_timeline_zoom_readout()

    def zoom_timeline_in(self) -> None:
        self._set_timeline_zoom_factor(self._timeline_zoom_factor() * float(self._timeline_zoom_step_ratio))
        self.update_status(f"Timeline zoom: {int(round(self._timeline_zoom_factor() * 100.0))}%")

    def zoom_timeline_out(self) -> None:
        self._set_timeline_zoom_factor(self._timeline_zoom_factor() / float(self._timeline_zoom_step_ratio))
        self.update_status(f"Timeline zoom: {int(round(self._timeline_zoom_factor() * 100.0))}%")

    def reset_timeline_zoom(self) -> None:
        self._set_timeline_zoom_factor(1.0)
        self.update_status("Timeline zoom reset to 100%")

    def _on_timeline_zoom_request(self, steps: int, anchor_x: int) -> None:
        step_count = max(1, abs(int(steps)))
        if int(steps) >= 0:
            target_zoom = self._timeline_zoom_factor() * (float(self._timeline_zoom_step_ratio) ** step_count)
        else:
            target_zoom = self._timeline_zoom_factor() / (float(self._timeline_zoom_step_ratio) ** step_count)
        self._set_timeline_zoom_factor(target_zoom, anchor_view_x=int(anchor_x))
        self.update_status(f"Timeline zoom: {int(round(self._timeline_zoom_factor() * 100.0))}%")

    def _connect_timeline_controller_bridge(self) -> None:
        timeline_controller = getattr(self, "timeline_controller", None)
        if timeline_controller is None or self._timeline_controller_bridge_connected:
            return
        if not hasattr(self, "timeline_scroll"):
            return

        timeline_controller.playhead_changed.connect(self._on_timeline_controller_playhead_changed)
        timeline_controller.zoom_factor_changed.connect(self._on_timeline_controller_zoom_changed)
        timeline_controller.scroll_position_changed.connect(self._on_timeline_controller_scroll_changed)
        self.timeline_scroll.horizontalScrollBar().valueChanged.connect(self._on_timeline_scroll_bar_value_changed)
        self._timeline_controller_bridge_connected = True

        self._on_timeline_controller_scroll_changed(int(timeline_controller.get_scroll_position()))
        self._on_timeline_controller_playhead_changed(int(timeline_controller.get_playhead()))
        self._on_timeline_controller_zoom_changed(float(timeline_controller.get_zoom_factor()))

    def _on_timeline_controller_playhead_changed(self, playhead_ms: int) -> None:
        self._set_project_playhead_ms(int(playhead_ms), sync_controller=False)

    def _on_timeline_controller_zoom_changed(self, zoom_factor: float) -> None:
        if hasattr(self, "timeline"):
            self.timeline.set_zoom_factor(float(zoom_factor))
        self._update_timeline_zoom_readout()

    def _on_timeline_controller_scroll_changed(self, scroll_position_px: int) -> None:
        if not hasattr(self, "timeline_scroll"):
            return
        bar = self.timeline_scroll.horizontalScrollBar()
        clamped_value = max(bar.minimum(), min(int(scroll_position_px), bar.maximum()))
        if bar.value() == clamped_value:
            return
        self._syncing_timeline_scroll = True
        try:
            bar.setValue(clamped_value)
        finally:
            self._syncing_timeline_scroll = False

    def _on_timeline_scroll_bar_value_changed(self, value: int) -> None:
        if self._syncing_timeline_scroll:
            return
        timeline_controller = getattr(self, "timeline_controller", None)
        if timeline_controller is not None:
            timeline_controller.set_scroll_position(int(value))

    def _default_skip_step_ms(self) -> int:
        timeline_controller = getattr(self, "timeline_controller", None)
        bpm = 120.0
        time_signature = "4/4"
        if timeline_controller is not None:
            bpm = float(timeline_controller.get_bpm())
            time_signature = str(timeline_controller.get_time_signature())
        numerator_text, _, denominator_text = time_signature.partition("/")
        try:
            numerator = max(1, int(numerator_text))
        except ValueError:
            numerator = 4
        try:
            denominator = max(1, int(denominator_text or "4"))
        except ValueError:
            denominator = 4
        beat_seconds = 60.0 / max(1.0, bpm)
        bar_seconds = beat_seconds * float(numerator) * (4.0 / float(denominator))
        return max(250, int(round(bar_seconds * 1000.0)))

    def _on_timeline_time_range_changed(
        self,
        track_index: Optional[int],
        start_ms: Optional[int],
        end_ms: Optional[int],
    ) -> None:
        if not hasattr(self, "comp_start_sec_input") or not hasattr(self, "comp_end_sec_input"):
            return
        if track_index is None or start_ms is None or end_ms is None:
            self.comp_start_sec_input.setText("")
            self.comp_end_sec_input.setText("")
            return
        self.comp_start_sec_input.setText(f"{max(0, int(start_ms)) / 1000.0:.3f}")
        self.comp_end_sec_input.setText(f"{max(0, int(end_ms)) / 1000.0:.3f}")

    def _current_transport_target_range(self) -> Tuple[int, int, str]:
        selected_range = self.timeline.get_selected_time_range_ms()
        if selected_range is not None:
            start_ms, end_ms = selected_range
            return int(start_ms), int(end_ms), "selection"

        clip_range = self.timeline.get_selected_clip_range_ms()
        if clip_range is not None:
            start_ms, end_ms = clip_range
            return int(start_ms), int(end_ms), "clip"

        project_end_ms = project_duration_ms(self.current_project)
        return 0, int(project_end_ms), "project"

    def jump_to_transport_start(self) -> None:
        start_ms, _end_ms, source = self._current_transport_target_range()
        if source == "project":
            step_ms = self._default_skip_step_ms()
            target_ms = max(0, int(self.project_playhead_ms) - int(step_ms))
            self._set_project_playhead_ms(int(target_ms))
            self.update_status(f"Skipped back {step_ms / 1000.0:.2f}s to {target_ms / 1000.0:.2f}s")
            return
        self._set_project_playhead_ms(int(start_ms))
        self.update_status(f"Moved playhead to {source} start at {start_ms / 1000.0:.2f}s")

    def jump_to_transport_end(self) -> None:
        _start_ms, end_ms, source = self._current_transport_target_range()
        if source == "project":
            step_ms = self._default_skip_step_ms()
            project_end_ms = int(project_duration_ms(self.current_project))
            target_ms = min(project_end_ms, int(self.project_playhead_ms) + int(step_ms))
            self._set_project_playhead_ms(int(target_ms))
            self.update_status(f"Skipped forward {step_ms / 1000.0:.2f}s to {target_ms / 1000.0:.2f}s")
            return
        self._set_project_playhead_ms(int(end_ms))
        self.update_status(f"Moved playhead to {source} end at {end_ms / 1000.0:.2f}s")

    def _update_project_playback_controls(self, is_playing: bool) -> None:
        self.play_project_btn.setEnabled(not is_playing)
        self.stop_project_btn.setEnabled(is_playing)

    def _is_project_playback_running(self) -> bool:
        return bool(self._project_playback_started_at is not None and is_playback_active())

    def _refresh_active_project_playback_mix(self, reason: str) -> bool:
        if not self._is_project_playback_running():
            return False

        elapsed_ms = int(max(0.0, (time.monotonic() - float(self._project_playback_started_at or 0.0)) * 1000.0))
        current_ms = min(int(self._project_playback_end_ms), int(self._project_playback_start_ms) + elapsed_ms)
        self._set_project_playhead_ms(current_ms)

        try:
            played_duration_ms = play_project(self.current_project, start_ms=int(current_ms), blocking=False)
        except Exception as exc:
            QMessageBox.critical(self, "Playback error", f"Could not refresh playback mix:\n{exc}")
            self.update_status("Playback remix failed")
            return False

        if played_duration_ms <= 0:
            self._finish_project_playback(stopped_manually=True)
            return False

        self._project_playback_segment = self._render_project_playback_segment(start_ms=int(current_ms), end_ms=None)
        self._project_playback_lufs_integrated_db = -70.0
        self._project_playback_start_ms = int(current_ms)
        self._project_playback_end_ms = int(current_ms) + int(played_duration_ms)
        self._project_playback_manual_stop = False
        self._project_playback_started_at = time.monotonic()
        self._update_project_playback_controls(True)
        self.project_playback_timer.start()
        self._update_master_playback_visuals()
        self.update_status(f"Applied {reason}; playback remixed from {current_ms / 1000.0:.2f}s")
        return True

    def _finish_project_playback(self, *, stopped_manually: bool) -> None:
        self.project_playback_timer.stop()
        if self._project_playback_started_at is not None:
            elapsed_ms = int(max(0.0, (time.monotonic() - self._project_playback_started_at) * 1000.0))
            current_ms = min(self._project_playback_end_ms, self._project_playback_start_ms + elapsed_ms)
            self._set_project_playhead_ms(current_ms)
        if not stopped_manually:
            self._set_project_playhead_ms(self._project_playback_end_ms)
            self.update_status("Playback finished")
        else:
            self.update_status(f"Playback stopped at {self.project_playhead_ms / 1000.0:.2f}s")
        self._project_playback_started_at = None
        self._project_playback_manual_stop = False
        self._project_playback_segment = None
        mixer_layout = getattr(self, "main_mixer_view", None)
        if mixer_layout is not None and hasattr(mixer_layout, "reset_master_playback_metrics"):
            mixer_layout.reset_master_playback_metrics()
        self._update_project_playback_controls(False)
        self._refresh_application_state_machine()

    def _poll_project_playback(self) -> None:
        if self._project_playback_started_at is None:
            self.project_playback_timer.stop()
            self._update_project_playback_controls(False)
            return

        elapsed_ms = int(max(0.0, (time.monotonic() - self._project_playback_started_at) * 1000.0))
        current_ms = min(self._project_playback_end_ms, self._project_playback_start_ms + elapsed_ms)
        self._set_project_playhead_ms(current_ms)
        self._update_master_playback_visuals()

        if not is_playback_active():
            self._finish_project_playback(stopped_manually=self._project_playback_manual_stop)

    def _render_project_playback_segment(self, *, start_ms: int, end_ms: Optional[int]) -> np.ndarray:
        mix = mix_project_to_segment(self.current_project)
        if mix.shape[0] == 0:
            return np.zeros((0, 2), dtype=np.float32)
        start_frame = min(max(0, int(round((float(start_ms) / 1000.0) * TARGET_SAMPLE_RATE))), mix.shape[0])
        end_frame = mix.shape[0]
        if end_ms is not None:
            end_frame = min(
                max(start_frame, int(round((float(max(0, int(end_ms))) / 1000.0) * TARGET_SAMPLE_RATE))),
                mix.shape[0],
            )
        return mix[start_frame:end_frame, :]

    def _waveform_preview_from_window(self, window: np.ndarray, columns: int = 12) -> str:
        if window.shape[0] <= 0:
            return "▁" * int(columns)
        mono = np.mean(np.abs(window), axis=1)
        if mono.size <= 0:
            return "▁" * int(columns)
        sample_positions = np.linspace(0, mono.size - 1, int(max(2, columns)), dtype=np.int32)
        sampled = mono[sample_positions]
        glyphs = "▁▂▃▄▅▆▇█"
        out = []
        for value in sampled:
            normalized = max(0.0, min(1.0, float(value)))
            idx = min(len(glyphs) - 1, int(round(normalized * (len(glyphs) - 1))))
            out.append(glyphs[idx])
        return "".join(out)

    def _update_master_playback_visuals(self) -> None:
        if not self._is_project_playback_running() or self._project_playback_segment is None:
            return
        segment = self._project_playback_segment
        if segment.shape[0] <= 0:
            return

        elapsed_ms = int(max(0.0, (time.monotonic() - float(self._project_playback_started_at or 0.0)) * 1000.0))
        elapsed_frames = int(round((float(elapsed_ms) / 1000.0) * TARGET_SAMPLE_RATE))
        frame_index = max(1, min(segment.shape[0], elapsed_frames))
        window_frames = max(256, int(round(0.05 * TARGET_SAMPLE_RATE)))
        start = max(0, frame_index - window_frames)
        meter_window = segment[start:frame_index, :]
        if meter_window.shape[0] <= 0:
            return

        rms_left = float(np.sqrt(np.mean(np.square(meter_window[:, 0], dtype=np.float64))) + 1e-12)
        rms_right = float(np.sqrt(np.mean(np.square(meter_window[:, 1], dtype=np.float64))) + 1e-12)
        left_db = max(-60.0, min(6.0, 20.0 * float(np.log10(rms_left))))
        right_db = max(-60.0, min(6.0, 20.0 * float(np.log10(rms_right))))

        peak_left = float(np.max(np.abs(meter_window[:, 0]))) if meter_window.shape[0] > 0 else 0.0
        peak_right = float(np.max(np.abs(meter_window[:, 1]))) if meter_window.shape[0] > 0 else 0.0
        peak_left_db = max(-80.0, min(6.0, 20.0 * float(np.log10(peak_left + 1e-12))))
        peak_right_db = max(-80.0, min(6.0, 20.0 * float(np.log10(peak_right + 1e-12))))

        loudness_proxy = max(left_db, right_db)
        alpha = 0.985
        self._project_playback_lufs_integrated_db = (
            alpha * float(self._project_playback_lufs_integrated_db)
        ) + ((1.0 - alpha) * float(loudness_proxy))
        display_lufs = max(-70.0, min(3.0, float(self._project_playback_lufs_integrated_db) - 0.8))
        waveform_preview = self._waveform_preview_from_window(meter_window, columns=12)
        self._master_short_term_lufs_db = max(-70.0, min(3.0, float(display_lufs) + 0.8))
        self._master_momentary_lufs_db = max(-70.0, min(3.0, float(display_lufs) + 1.4))
        self._master_lufs_range_db = max(0.0, min(24.0, abs(float(left_db) - float(right_db)) + 1.5))
        self._master_true_peak_db = max(float(peak_left_db), float(peak_right_db))

        mixer_layout = getattr(self, "main_mixer_view", None)
        if mixer_layout is not None and hasattr(mixer_layout, "update_master_playback_metrics"):
            mixer_layout.update_master_playback_metrics(
                left_db=float(left_db),
                right_db=float(right_db),
                peak_left_db=float(peak_left_db),
                peak_right_db=float(peak_right_db),
                lufs_integrated_db=float(display_lufs),
                waveform_preview=waveform_preview,
            )

    def stop_current_project_playback(self) -> None:
        if self._project_playback_started_at is None and not is_playback_active():
            self.update_status("Playback is not running")
            return
        self._project_playback_manual_stop = True
        stop_playback()
        self._finish_project_playback(stopped_manually=True)

    def refresh_timeline(self):
        self.timeline.set_project(self.current_project)
        self.timeline.set_selected_track(self.selected_track_index)
        self._set_project_playhead_ms(self.project_playhead_ms)
        self.timeline.clear_automation_points()
        self.timeline.clear_comp_regions()
        for track_id in range(len(self.current_project.tracks)):
            comp_regions = self.recording_controller.session.get_comp_regions_for_track(int(track_id))
            serialized = [
                {
                    "region_id": int(region.region_id),
                    "start_ms": int(region.start_ms),
                    "end_ms": int(region.end_ms),
                    "source_take_number": int(region.source_take_number),
                    "enabled": bool(region.enabled),
                }
                for region in comp_regions
                if bool(region.enabled)
            ]
            self.timeline.set_comp_regions_for_track(int(track_id), serialized)
            parameter = self._track_automation_parameter(int(track_id))
            self.timeline.set_active_automation_parameter(int(track_id), parameter)
            self.timeline.set_track_automation_points(
                int(track_id),
                parameter,
                self._track_automation_points(int(track_id), parameter),
            )
        self.timeline.updateGeometry()
        self.timeline.update()
        mixer_layout = getattr(self, "main_mixer_view", None)
        if mixer_layout is not None:
            if hasattr(mixer_layout, "set_timeline_content_width"):
                mixer_layout.set_timeline_content_width(int(self.timeline.width()))
            if hasattr(mixer_layout, "_sync_master_processing_from_window"):
                mixer_layout._sync_master_processing_from_window()
        timeline_controller = getattr(self, "timeline_controller", None)
        if timeline_controller is not None:
            self._on_timeline_controller_scroll_changed(int(timeline_controller.get_scroll_position()))
        fade_state = self._clip_fade_edit_state
        if fade_state is not None:
            clip_id = int(fade_state.get("clip_id", -1))
            if self._find_clip_by_id(clip_id) is None:
                self._clip_fade_edit_state = None
        if self._clip_fade_popover is not None and self._clip_fade_popover.isVisible():
            popover_clip_id = self._clip_fade_popover.clip_id()
            if popover_clip_id is None or self._find_clip_by_id(int(popover_clip_id)) is None:
                self._clip_fade_popover.hide()
            else:
                self._sync_fade_popover_from_clip(int(popover_clip_id))

    def _parse_int_field(self, text: str, *, field_name: str, allow_empty: bool = False, default_value: Optional[int] = None) -> Optional[int]:
        value = text.strip()
        if not value:
            if allow_empty:
                return default_value
            QMessageBox.warning(self, "Input error", f"{field_name} is required.")
            return None
        parsed = parse_int(value)
        if parsed is None:
            QMessageBox.warning(self, "Input error", f"{field_name} must be a whole number.")
            return None
        return parsed

    def _parse_float_field(self, text: str, *, field_name: str, allow_empty: bool = False, default_value: Optional[float] = None) -> Optional[float]:
        value = text.strip()
        if not value:
            if allow_empty:
                return default_value
            QMessageBox.warning(self, "Input error", f"{field_name} is required.")
            return None
        parsed = parse_float(value)
        if parsed is None:
            QMessageBox.warning(self, "Input error", f"{field_name} must be numeric.")
            return None
        return parsed

    def _parse_time_signature(self, text: str, *, field_name: str = "Time signature") -> Optional[str]:
        parsed = parse_time_signature(text)
        if parsed is None:
            QMessageBox.warning(self, "Input error", f"{field_name} must look like 4/4.")
            return None
        numerator, denominator = parsed
        return f"{numerator}/{denominator}"

    def _parse_track_index(self, text: str, *, field_name: str = "Track index") -> Optional[int]:
        parsed = self._parse_int_field(text, field_name=field_name)
        if parsed is None:
            return None
        if parsed < 0 or parsed >= len(self.current_project.tracks):
            QMessageBox.warning(self, "Input error", f"{field_name} is out of range.")
            return None
        return parsed

    def _restore_song_generation_metadata(self) -> None:
        metadata = self.current_project.metadata.get("song_generation_state")
        self.last_song_generation = metadata if isinstance(metadata, dict) else None

    def _persist_song_generation_metadata(self) -> None:
        if self.last_song_generation:
            self.current_project.metadata["song_generation_state"] = self.last_song_generation
        else:
            self.current_project.metadata.pop("song_generation_state", None)

    def _default_new_project_folder(self) -> Path:
        if self._project_save_directory is not None:
            return Path(self._project_save_directory)
        try:
            PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return Path(PROJECTS_DIR)

    def _build_new_project_template_tracks(self, template_id: str) -> list[Track]:
        def _mk(track_name: str, track_type: str, color_hex: str) -> Track:
            default_input, _can_arm = self._track_runtime_policy(track_type)
            return Track(name=track_name, track_type=track_type, color_hex=color_hex, input_source=default_input)

        normalized = str(template_id or "empty").strip().lower()
        if normalized == "basic_4_track":
            return [
                _mk("Audio 1", "Audio", "#00F0FF"),
                _mk("Audio 2", "Audio", "#44D0FF"),
                _mk("Audio 3", "Audio", "#4DD78B"),
                _mk("Audio 4", "Audio", "#D8AA49"),
            ]
        if normalized == "podcast":
            return [
                _mk("Host Mic", "Audio", "#00F0FF"),
                _mk("Guest Mic", "Audio", "#44D0FF"),
                _mk("Music Bed", "Bus", "#D8AA49"),
                _mk("SFX", "Audio", "#FF8A65"),
            ]
        if normalized == "beat_maker":
            return [
                _mk("Drums", "Audio", "#FF6F61"),
                _mk("Bass", "Audio", "#F6BD60"),
                _mk("Melody", "MIDI", "#A280FF"),
                _mk("Vox", "Audio", "#8BD3DD"),
            ]
        if normalized == "ai_stems_session":
            return [
                _mk("Reference Mix", "Audio", "#00F0FF"),
                _mk("Vocals Stem", "AI Stem", "#44D07A"),
                _mk("Drums Stem", "AI Stem", "#F6BD60"),
                _mk("Bass Stem", "AI Stem", "#4DD7FF"),
                _mk("Other Stem", "AI Stem", "#C78BFF"),
            ]
        return []

    def _apply_new_project_audio_defaults(self, *, bpm: int, sample_rate: int) -> None:
        self.recording_controller.set_tempo(int(bpm))
        self.recording_controller.set_time_signature(4, 4)
        if hasattr(self, "sample_rate_combo"):
            target_idx = self.sample_rate_combo.findData(int(sample_rate))
            if target_idx >= 0:
                self.sample_rate_combo.setCurrentIndex(int(target_idx))
            else:
                device_manager.set_sample_rate(int(sample_rate))
        else:
            device_manager.set_sample_rate(int(sample_rate))

        timeline_controller = getattr(self, "timeline_controller", None)
        if timeline_controller is not None:
            timeline_controller.set_bpm(float(bpm))
            timeline_controller.set_time_signature("4/4")
            timeline_controller.set_sample_rate(int(sample_rate))

    def _create_project_from_dialog_config(self, config: dict) -> None:
        project_name = str(config.get("project_name", "Untitled") or "Untitled").strip() or "Untitled"
        template_id = str(config.get("template_id", "empty") or "empty").strip().lower()
        selected_folder = Path(str(config.get("project_folder", self._default_new_project_folder())))
        sample_rate = int(config.get("sample_rate", 44100) or 44100)
        bpm = int(config.get("bpm", 120) or 120)

        if self._project_playback_started_at is not None or is_playback_active():
            self.stop_current_project_playback()

        self.current_project = new_empty_project(project_name)
        self.current_project.tracks = self._build_new_project_template_tracks(template_id)
        self.current_project.metadata["project_template"] = template_id
        self.current_project.metadata["project_sample_rate"] = int(sample_rate)
        self.current_project.metadata["project_tempo_bpm"] = int(bpm)
        self.current_project.metadata["project_folder"] = str(selected_folder)
        self.project_name_label.setText(f"Project: {project_name}")

        self.next_clip_id = 1
        self.last_song_generation = None
        self.project_playhead_ms = 0
        self._persist_song_generation_metadata()
        self.recording_controller = RecordingController("new_session", self.current_project.name)
        self.recording_controller.restore_session_preferences()
        self._apply_new_project_audio_defaults(bpm=int(bpm), sample_rate=int(sample_rate))
        self._clear_project_history()
        self.selected_track_index = None
        self._project_save_directory = selected_folder

        for track_idx in range(len(self.current_project.tracks)):
            self.recording_controller.session.ensure_track(int(track_idx))

        self.sync_project_tracks_to_recording_engine()
        self.sync_recording_controls_from_controller()
        self._build_recording_meters()
        rebuild_mixer_rows = getattr(self, "_rebuild_mixer_rows", None)
        if callable(rebuild_mixer_rows):
            rebuild_mixer_rows()
        self._apply_take_review_preferences()
        self.refresh_track_list()
        self.refresh_take_track_selector()
        self.refresh_take_review_list()
        self.refresh_alter_section_selector()
        self.update_recording_status_label()
        self._prompt_recovery_for_current_session()
        self.refresh_recovery_history()
        self.refresh_timeline()
        self._saved_project_fingerprint = None
        self._refresh_status_bar_telemetry()
        template_label = template_id.replace("_", " ").title()
        self.update_status(f"New project created: {project_name} ({template_label}, {sample_rate} Hz, {bpm} BPM)")

    def new_project(self):
        default_sample_rate = int(device_manager.selected_sample_rate)
        if hasattr(self, "sample_rate_combo"):
            selected_sample_rate = self.sample_rate_combo.currentData()
            if isinstance(selected_sample_rate, int) and selected_sample_rate > 0:
                default_sample_rate = int(selected_sample_rate)

        default_bpm = int(self.recording_controller.status.current_tempo_bpm)
        timeline_controller = getattr(self, "timeline_controller", None)
        if timeline_controller is not None:
            default_bpm = int(round(float(timeline_controller.get_bpm())))

        dialog = NewProjectDialog(
            initial_name="Untitled",
            initial_folder=self._default_new_project_folder(),
            initial_sample_rate=int(default_sample_rate),
            initial_bpm=int(default_bpm),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or not isinstance(dialog.result_config, dict):
            self.update_status("New project creation cancelled")
            return
        self._create_project_from_dialog_config(dialog.result_config)

    def open_project(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Echo Pro Project",
            "",
            "Echo Projects (*.eproj);;All Files (*)"
        )
        if not filename:
            return
        try:
            if self._project_playback_started_at is not None or is_playback_active():
                self.stop_current_project_playback()
            proj = load_project(Path(filename))
            self.current_project = proj
            self._project_save_directory = Path(filename).resolve().parent
            self.project_name_label.setText(f"Project: {proj.name}")
            self._restore_song_generation_metadata()
            self.project_playhead_ms = 0
            max_id = 0
            for c in proj.clips:
                if c.id > max_id:
                    max_id = c.id
            self.next_clip_id = max_id + 1
            self.recording_controller = RecordingController(f"session_{proj.name.replace(' ', '_')}", proj.name)
            self.recording_controller.restore_session_preferences()
            self._clear_project_history()
            self.selected_track_index = None
            self.sync_project_tracks_to_recording_engine()
            self.sync_recording_controls_from_controller()
            self._build_recording_meters()
            self._apply_take_review_preferences()
            self.refresh_track_list()
            self.refresh_take_track_selector()
            self.refresh_take_review_list()
            self.refresh_alter_section_selector()
            self.update_recording_status_label()
            self._prompt_recovery_for_current_session()
            self.refresh_recovery_history()
            self.refresh_timeline()
            self._mark_project_saved_state()
            self.update_status(f"Opened project: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")

    def save_project_dialog(self):
        default_dir = self._project_save_directory if self._project_save_directory is not None else PROJECTS_DIR
        initial_path = str(Path(default_dir) / f"{self.current_project.name or 'Untitled'}.eproj")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Echo Pro Project",
            initial_path,
            "Echo Projects (*.eproj)"
        )
        if not filename:
            return
        if not filename.lower().endswith(".eproj"):
            filename += ".eproj"
        try:
            path = Path(filename)
            self.current_project.name = path.stem
            self.current_project.metadata["project_folder"] = str(path.parent)
            self._project_save_directory = path.resolve().parent
            save_project(self.current_project, path)
            self.project_name_label.setText(f"Project: {self.current_project.name}")
            self._mark_project_saved_state()
            self.update_status(f"Saved project: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{e}")

    def browse_projects(self):
        dlg = ProjectBrowserDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_path:
            filename = dlg.selected_path
            try:
                if self._project_playback_started_at is not None or is_playback_active():
                    self.stop_current_project_playback()
                proj = load_project(Path(filename))
                self.current_project = proj
                self._project_save_directory = Path(filename).resolve().parent
                self.project_name_label.setText(f"Project: {proj.name}")
                self._restore_song_generation_metadata()
                self.project_playhead_ms = 0
                max_id = 0
                for c in proj.clips:
                    if c.id > max_id:
                        max_id = c.id
                self.next_clip_id = max_id + 1
                self.recording_controller = RecordingController(f"session_{proj.name.replace(' ', '_')}", proj.name)
                self.recording_controller.restore_session_preferences()
                self._clear_project_history()
                self.selected_track_index = None
                self.sync_project_tracks_to_recording_engine()
                self.sync_recording_controls_from_controller()
                self._build_recording_meters()
                self._apply_take_review_preferences()
                self.refresh_track_list()
                self.refresh_take_track_selector()
                self.refresh_take_review_list()
                self.refresh_alter_section_selector()
                self.update_recording_status_label()
                self._prompt_recovery_for_current_session()
                self.refresh_recovery_history()
                self.refresh_timeline()
                self._mark_project_saved_state()
                self.update_status(f"Opened project from library: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")

    def add_track(self):
        name = self.track_name_input.text().strip()
        self._add_track_with_type("Audio", name=name if name else None, clear_name_input=True)

    def _prompt_track_type(self) -> Optional[str]:
        options = ["Audio", "AI Stem", "MIDI", "Bus"]
        selected, accepted = QInputDialog.getItem(
            self,
            "Add Track",
            "Track type",
            options,
            current=0,
            editable=False,
        )
        if not accepted:
            return None
        track_type = str(selected).strip()
        return self._normalize_track_type_label(track_type)

    def _normalize_track_type_label(self, track_type: str) -> str:
        normalized = str(track_type).strip().lower()
        if normalized == "ai stem":
            return "AI Stem"
        if normalized == "midi":
            return "MIDI"
        if normalized == "bus":
            return "Bus"
        return "Audio"

    def _track_runtime_policy(self, track_type: str) -> tuple[str, bool]:
        normalized = self._normalize_track_type_label(track_type)
        if normalized == "AI Stem":
            return "Stem", False
        if normalized == "MIDI":
            return "MIDI", False
        if normalized == "Bus":
            return "Bus", False
        return "Auto", True

    def _enforce_track_runtime_policy(self, track_index: int, track: Track) -> None:
        track_type = self._normalize_track_type_label(getattr(track, "track_type", "Audio"))
        track.track_type = track_type
        expected_input_source, can_arm = self._track_runtime_policy(track_type)
        if track.input_source != expected_input_source:
            track.input_source = expected_input_source
        if not can_arm and track_index in self.recording_controller.armed_tracks:
            self.recording_controller.disarm_track(track_index)

    def _track_defaults_for_type(self, track_type: str) -> tuple[str, str]:
        normalized = self._normalize_track_type_label(track_type)
        if normalized == "AI Stem":
            return "#44D07A", "Stem"
        if normalized == "MIDI":
            return "#A280FF", "MIDI"
        if normalized == "Bus":
            return "#D8AA49", "Bus"
        return "#00F0FF", "Auto"

    def _add_track_with_type(self, track_type: str, *, name: Optional[str] = None, clear_name_input: bool = False, capture_history: bool = True) -> None:
        type_label = self._normalize_track_type_label(track_type)
        color_hex, input_source = self._track_defaults_for_type(type_label)
        track_index = len(self.current_project.tracks)
        default_name = f"{type_label} {track_index + 1}"
        track_name = str(name).strip() if name is not None else ""
        if not track_name:
            track_name = default_name

        if capture_history:
            self._mark_project_edit(f"Add {type_label} track")

        self.current_project.tracks.append(
            Track(name=track_name, track_type=type_label, color_hex=color_hex, input_source=input_source)
        )
        self.recording_controller.session.ensure_track(len(self.current_project.tracks) - 1)
        self.selected_track_index = len(self.current_project.tracks) - 1
        if clear_name_input and hasattr(self, "track_name_input"):
            self.track_name_input.clear()
        self.sync_project_tracks_to_recording_engine()
        self._build_recording_meters()
        self.refresh_track_list()
        self.refresh_timeline()
        self.update_status(f"Added {type_label} track: {track_name}")

    def _on_add_track_from_mixer(self) -> None:
        track_type = self._prompt_track_type()
        if track_type is None:
            return
        self._add_track_with_type(track_type)

    def _build_add_track_strip_widget(self) -> QWidget:
        strip = QFrame()
        strip.setObjectName("AddTrackStrip")
        strip.setFixedWidth(220)
        strip.setMinimumHeight(520)
        strip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        strip.setStyleSheet(
            "QFrame#AddTrackStrip { background:#111923; border:1px dashed #2D3A4A; border-radius:6px; }"
            "QLabel#AddTrackStripHint { color:#6f8398; font-size:9px; }"
            "QPushButton#AddTrackStripButton { background:#1C2B3B; border:1px solid #3D5D7A; color:#D9E8F6; font-weight:bold; border-radius:4px; }"
            "QPushButton#AddTrackStripButton:hover { border-color:#74C7FF; color:#FFFFFF; }"
            "QPushButton#AddTrackStripButton:pressed { background:#22384D; }"
        )
        layout = QVBoxLayout(strip)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("TRACKS")
        title.setStyleSheet("color:#7f94a9; font-size:10px; font-weight:bold; letter-spacing:1px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        hint = QLabel("Add a new channel strip")
        hint.setObjectName("AddTrackStripHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        layout.addStretch()

        add_button = QPushButton("+ Add Track")
        add_button.setObjectName("AddTrackStripButton")
        add_button.setToolTip("Add a new track and choose its type (Audio / AI Stem / MIDI / Bus)")
        add_button.clicked.connect(self._on_add_track_from_mixer)
        add_button.setMinimumHeight(38)
        layout.addWidget(add_button)

        return strip

    def add_clip_from_file(self):
        track_index = self._parse_track_index(self.clip_track_index_input.text(), field_name="Track index")
        if track_index is None:
            return

        start_sec = self._parse_float_field(
            self.clip_start_sec_input.text(),
            field_name="Start time (seconds)",
            allow_empty=True,
            default_value=0.0,
        )
        if start_sec is None:
            return
        if start_sec < 0:
            QMessageBox.warning(self, "Input error", "Start time must be zero or greater.")
            return

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choose audio file for clip",
            "",
            "Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)"
        )
        if not filename:
            return
        file_path = Path(filename)
        if not file_path.exists():
            QMessageBox.warning(self, "Input error", "Selected file does not exist.")
            return

        try:
            length_ms = get_audio_length_ms(str(file_path))
            start_ms = int(start_sec * 1000)
            self._mark_project_edit(f"Add clip to track {track_index + 1}")
            clip = Clip(
                id=self.next_clip_id,
                track_index=track_index,
                file_path=str(file_path),
                start_ms=start_ms,
                length_ms=length_ms
            )
            self.current_project.clips.append(clip)
            self.next_clip_id += 1
            self.refresh_timeline()
            self.update_status(f"Added clip on track {track_index} from {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add clip:\n{e}")

    def set_track_volume(self):
        track_index = self._parse_track_index(self.volume_track_index_input.text(), field_name="Track index")
        if track_index is None:
            return

        db = self._parse_float_field(self.volume_db_input.text(), field_name="Volume dB")
        if db is None:
            return

        self.current_project.tracks[track_index].volume_db = db
        self.sync_project_tracks_to_recording_engine()
        self.refresh_track_list()
        self.refresh_timeline()
        self._refresh_active_project_playback_mix(f"track {track_index + 1} volume")
        self.update_status(f"Track {track_index} volume set to {db} dB")

    def play_current_project(self):
        if self._project_playback_started_at is not None or is_playback_active():
            self.stop_current_project_playback()

        start_ms = int(self.project_playhead_ms)
        self.update_status(f"Mixing and playing project from {start_ms / 1000.0:.2f}s...")
        QApplication.processEvents()
        try:
            played_duration_ms = play_project(self.current_project, start_ms=start_ms, blocking=False)
            if played_duration_ms <= 0:
                self.update_status("Nothing to play from the current playhead position")
                return
            self._project_playback_segment = self._render_project_playback_segment(start_ms=int(start_ms), end_ms=None)
            self._project_playback_lufs_integrated_db = -70.0
            self._project_playback_start_ms = start_ms
            self._project_playback_end_ms = start_ms + int(played_duration_ms)
            self._project_playback_manual_stop = False
            self._project_playback_started_at = time.monotonic()
            self._update_project_playback_controls(True)
            self.project_playback_timer.start()
            self._update_master_playback_visuals()
        except Exception as e:
            QMessageBox.critical(self, "Playback error", f"Could not play project:\n{e}")
            self.update_status("Playback error")

    def _run_dependency_update_dialog(self, action: str = "update") -> bool:
        script_path = Path(__file__).resolve().parent / "install_echo_pro.bat"
        if not script_path.exists():
            QMessageBox.critical(self, "Dependency update", f"Installer script not found:\n{script_path}")
            return False

        progress = QProgressDialog("Preparing dependency update...", "Cancel", 0, 6, self)
        progress.setWindowTitle("Dependency setup")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        step_value = 0
        step_markers = [
            ("Checking ffmpeg...", 0),
            ("ffmpeg ready", 1),
            ("Using existing runtime Python", 2),
            ("Creating local runtime venv...", 2),
            ("Installing/updating demucs", 3),
            ("demucs ready", 3),
            ("Checking Demucs model assets...", 4),
            ("Demucs model assets ready", 4),
            ("Installing RVC reference model", 5),
            ("RVC ready", 5),
            ("Installing ACE Step 1.5 model assets", 6),
            ("ACE Step 1.5 ready", 6),
            ("Dependencies are ready.", 6),
        ]

        try:
            process = subprocess.Popen(
                [str(script_path), action],
                cwd=str(script_path.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as exc:
            progress.close()
            QMessageBox.critical(self, "Dependency update", f"Could not start dependency update:\n{exc}")
            return False

        output_lines: list[str] = []
        try:
            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                output_lines.append(line)
                progress.setLabelText(line)
                for marker, value in step_markers:
                    if marker in line:
                        step_value = max(step_value, value)
                        progress.setValue(step_value)
                        break
                QApplication.processEvents()
                if progress.wasCanceled():
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
                    QMessageBox.information(self, "Dependency update", "Dependency update was cancelled.")
                    return False
            process.wait()
        finally:
            progress.close()

        if process.returncode != 0:
            message = "\n".join(output_lines[-20:]) if output_lines else "Dependency update failed."
            QMessageBox.critical(self, "Dependency update", message)
            return False

        self.update_status("Dependencies updated.")
        return True

    def _split_song_into_stems_for_path(self, song_path: Path, *, allow_dependency_prompt: bool = True) -> None:
        if not song_path.exists():
            QMessageBox.warning(self, "Stems", "Selected song file does not exist.")
            return

        self._set_stem_source_path(song_path)
        selected_model = self._selected_demucs_model()

        progress = QProgressDialog("Preparing stem separation...", "Cancel", 0, 5, self)
        progress.setWindowTitle("Stem separation")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        try:
            stems_root = song_path.parent / "echo_stems"
            song_stems_dir = stems_root / song_path.stem
            runtime = resolve_stem_runtime()
            progress_steps = {
                "Starting Demucs separation": 1,
                "Launching Demucs": 1,
                "Downloading Demucs assets": 1,
                "Preparing output folder": 2,
                "Separating ": 2,
                "Demucs processing": 2,
                "Demucs backend": 2,
                "Collecting separated stem files": 3,
                "Demucs finished.": 4,
            }

            self._set_stem_status(
                f"Preparing Demucs split with {selected_model}.",
                detail=f"Source: {song_path.name}",
                reset_activity=True,
            )
            self.update_status("Running Demucs... this may take a while.")
            QApplication.processEvents()

            def _progress_message(text: str) -> None:
                progress.setLabelText(text)
                for marker, value in progress_steps.items():
                    if marker in text:
                        progress.setValue(max(progress.value(), value))
                        break
                self._set_stem_status(text, detail=text)
                QApplication.processEvents()

            stems = separate_stems(
                str(song_path),
                song_stems_dir,
                demucs_executable=runtime.demucs_executable,
                demucs_repo=runtime.demucs_repo,
                ffmpeg_executable=runtime.ffmpeg_executable,
                demucs_model=selected_model,
                progress_callback=_progress_message,
                cancel_check=progress.wasCanceled,
            )

            progress.setValue(max(progress.value(), 4))
            self.next_clip_id = add_stems_to_project(
                self.current_project,
                stems,
                song_stems_dir,
                next_clip_id_start=self.next_clip_id
            )

            self.sync_project_tracks_to_recording_engine()
            self.refresh_track_list()
            self.refresh_timeline()
            progress.setValue(5)
            stem_count = len(stems)
            self._set_stem_status(
                f"Stem split complete: {stem_count} stems ready from {song_path.name}.",
                detail=f"Added {stem_count} stems from {selected_model} into the project.",
            )
            self.update_status("Stems added to project.")
            QMessageBox.information(
                self,
                "Stems created",
                f"Demucs created {stem_count} stems and added them as tracks.\n"
                f"Output folder: {song_stems_dir}\n\n"
                "You can now edit them on the timeline."
            )
        except StemCancelledError as e:
            self._set_stem_status("Stem split cancelled.", detail=str(e))
            QMessageBox.information(self, "Stems", str(e))
            self.update_status("Stems cancelled")
        except StemDependencyError as e:
            self._set_stem_status("Stem backend needs setup.", detail=str(e))
            if allow_dependency_prompt:
                install_choice = QMessageBox.question(
                    self,
                    "Missing dependency",
                    f"{e}\n\nRun dependency update now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if install_choice == QMessageBox.StandardButton.Yes and self._run_dependency_update_dialog("update"):
                    self._split_song_into_stems_for_path(song_path, allow_dependency_prompt=False)
                    return
            self.update_status("Stems dependency issue")
        except StemSeparationError as e:
            self._set_stem_status("Stem split failed.", detail=str(e))
            QMessageBox.critical(self, "Error", f"Failed to split stems:\n{e}")
            self.update_status("Stems error")
        finally:
            progress.close()
            self._refresh_stem_section_state()

    def split_song_into_stems(self):
        if hasattr(self, "tabs") and hasattr(self, "stem_tab"):
            index = self.tabs.indexOf(self.stem_tab)
            if index >= 0:
                self.tabs.setCurrentIndex(index)

        if self.stem_source_path is None:
            self.choose_stem_source_audio()
        else:
            self._set_stem_status(
                "Stem source ready.",
                detail="Source selected. Click Run Stem Separation in the Stem Separation tab.",
            )

        self._refresh_stem_section_state()

    def open_voice_manager(self):
        dlg = VoiceManagerDialog(self)
        dlg.exec()
        self.update_status("Voice manager closed")

    def apply_voice_effect_to_clip(self):
        track_index = self._parse_track_index(self.voice_track_index_input.text(), field_name="Track index")
        if track_index is None:
            return
        clip_id = self._parse_int_field(self.voice_clip_id_input.text(), field_name="Clip ID")
        if clip_id is None:
            return
        profile_name = self.voice_profile_name_input.text().strip()
        if not profile_name:
            QMessageBox.warning(self, "Input error", "Please enter a voice profile name.")
            return

        target_clip = None
        for c in self.current_project.clips:
            if c.id == clip_id and c.track_index == track_index:
                target_clip = c
                break
        if target_clip is None:
            QMessageBox.warning(self, "Not found", "No clip found with that ID and track index.")
            return

        profiles = load_voice_profiles()
        selected_profile = None
        for p in profiles:
            if p.name == profile_name:
                selected_profile = p
                break

        if selected_profile is None:
            QMessageBox.warning(self, "Not found", "No voice profile with that name.")
            return

        if not selected_profile.consent_flag:
            QMessageBox.warning(
                self,
                "Consent required",
                "This voice profile is not marked as consented. Please confirm consent before using."
            )
            return

        backend_capability = get_voice_backend_capability()

        try:
            source_path = Path(target_clip.file_path)
            output_dir = source_path.parent / "echo_voice_outputs"
            output_path = output_dir / f"clip_{clip_id}_{profile_name.replace(' ', '_')}.wav"

            vp_config = VoiceProfileConfig(
                name=selected_profile.name,
                embedding_path=selected_profile.file_path,
                source_audio_path=selected_profile.file_path,
                consent_flag=True,
                source_type=selected_profile.source_type,
                metadata={}
            )

            result = apply_voice_conversion(
                source_wav=source_path,
                target_profile=vp_config,
                output_path=output_path,
                preserve_pitch=True,
                preserve_formants=True,
                strength=1.0,
                notes=f"Applied via Echo Pro to clip {clip_id}"
            )

            new_track_index = len(self.current_project.tracks)
            new_track_name = f"{profile_name} (converted)"
            self.current_project.tracks.append(Track(name=new_track_name))

            length_ms = get_audio_length_ms(str(result.audio_path))

            new_clip = Clip(
                id=self.next_clip_id,
                track_index=new_track_index,
                file_path=str(result.audio_path),
                start_ms=target_clip.start_ms,
                length_ms=length_ms
            )
            self.current_project.clips.append(new_clip)
            self.next_clip_id += 1

            self.sync_project_tracks_to_recording_engine()
            self.refresh_track_list()
            self.refresh_timeline()
            self.update_status(f"Voice conversion applied, new track: {new_track_name}")
            QMessageBox.information(
                self,
                "Voice conversion applied",
                "Voice conversion completed.\n"
                f"Backend: {result.backend_name}\n"
                f"Model ready: {backend_capability.get('ready', False)}\n"
                f"{backend_capability.get('reason', '')}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to apply voice conversion:\n{e}")
            self.update_status("Voice conversion error")

    def generate_single_clip(self, seed: Optional[int] = None, generation_metadata: Optional[dict] = None):
        try:
            style = self.gen_style.text().strip() or "ambient"
            genre = self.gen_genre.text().strip()
            mood = self.gen_mood.text().strip()
            lyrics = self.gen_lyrics.text().strip()
            duration_sec = self._parse_int_field(self.gen_duration.text(), field_name="Duration (sec)")
            if duration_sec is None:
                return
            if duration_sec < 10 or duration_sec > 300:
                QMessageBox.warning(self, "Input error", "Duration must be between 10 and 300 seconds.")
                return
            use_cloud = self.cloud_enabled.text().strip().lower() == "yes"
            capability = get_music_backend_capability()

            project_id = self.current_project.name.replace(" ", "_") or "default_project"

            progress = QProgressDialog("Generating music clip…", None, 0, 0, self)
            progress.setWindowTitle("Music Generation")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            progress.show()
            QApplication.processEvents()
            try:
                result = generate_music_clip(
                    style=style,
                    genre=genre,
                    mood=mood,
                    lyrics=lyrics,
                    duration_seconds=duration_sec,
                    key="",
                    chords="",
                    time_signature="4/4",
                    tempo_bpm=120,
                    section_name=f"clip_{self.next_clip_id}",
                    seed=seed,
                    project_id=project_id,
                    use_cloud=use_cloud,
                    output_format=str(self.ace_output_format_combo.currentText() or "wav").strip().lower() if hasattr(self, "ace_output_format_combo") else "wav",
                    output_sample_rate=int(self.ace_output_sample_rate_combo.currentData()) if hasattr(self, "ace_output_sample_rate_combo") and isinstance(self.ace_output_sample_rate_combo.currentData(), int) else 44100,
                    normalize_output=bool(self.ace_normalize_checkbox.isChecked()) if hasattr(self, "ace_normalize_checkbox") else True,
                )
                if generation_metadata:
                    metadata = dict(getattr(result, "metadata", {}) or {})
                    metadata["generation_payload"] = dict(generation_metadata)
                    result.metadata = metadata
            finally:
                progress.close()

            length_ms = get_audio_length_ms(str(result.audio_path))

            new_track_index = len(self.current_project.tracks)
            self.current_project.tracks.append(Track(name=f"Generated {self.next_clip_id}"))

            new_clip = Clip(
                id=self.next_clip_id,
                track_index=new_track_index,
                file_path=str(result.audio_path),
                start_ms=0,
                length_ms=length_ms
            )
            self.current_project.clips.append(new_clip)
            self.next_clip_id += 1

            self.sync_project_tracks_to_recording_engine()
            self.refresh_track_list()
            self.refresh_timeline()
            seed_suffix = f", seed {seed}" if seed is not None else ""
            self.update_status(f"Generated clip added to project (backend: {capability['backend']}{seed_suffix}).")
            if not capability["ready"]:
                QMessageBox.information(
                    self,
                    "Music backend status",
                    f"{capability['reason']}\n\nGenerated clip uses the current installed local backend until all optional assets are available.",
                )
            return result
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate clip:\n{e}")

    def generate_full_song(self):
        try:
            total_length_sec = self._parse_int_field(self.plan_total_length.text(), field_name="Total length (sec)")
            if total_length_sec is None:
                return
            if total_length_sec < 10:
                QMessageBox.warning(self, "Input error", "Total length must be at least 10 seconds.")
                return
            structure = [s.strip() for s in self.plan_structure.text().split(",") if s.strip()]
            if not structure:
                QMessageBox.warning(self, "Input error", "Enter at least one section in the structure.")
                return

            key = self.plan_key.text()
            chords = self.plan_chords.text()
            time_sig = self._parse_time_signature(self.plan_time_sig.text(), field_name="Generation time signature")
            if time_sig is None:
                return
            tempo = self._parse_int_field(self.plan_tempo.text(), field_name="Tempo (BPM)")
            if tempo is None:
                return
            if tempo <= 0:
                QMessageBox.warning(self, "Input error", "Tempo must be greater than zero.")
                return
            lyrics = self.plan_lyrics.toPlainText()

            use_cloud = self.cloud_enabled.text().strip().lower() == "yes"
            project_id = self.current_project.name.replace(" ", "_") or "default_project"

            style = self.gen_style.text()
            genre = self.gen_genre.text()
            mood = self.gen_mood.text()

            progress = QProgressDialog(
                f"Generating song ({len(structure)} sections)…", None, 0, 0, self
            )
            progress.setWindowTitle("Song Generation")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            progress.show()
            QApplication.processEvents()
            try:
                clip_paths = generate_song_sections(
                    lyrics=lyrics,
                    structure=structure,
                    total_length_sec=total_length_sec,
                    key=key,
                    chords=chords,
                    time_signature=time_sig,
                    tempo=tempo,
                    style=style,
                    genre=genre,
                    mood=mood,
                    project_id=project_id,
                    use_cloud=use_cloud
                )
            finally:
                progress.close()

            section_snapshots = []

            for section_index, path in enumerate(clip_paths):
                length_ms = get_audio_length_ms(str(path))
                new_track_index = len(self.current_project.tracks)
                section_name = structure[section_index]
                self.current_project.tracks.append(Track(name=f"Section {section_index}: {section_name}"))

                new_clip = Clip(
                    id=self.next_clip_id,
                    track_index=new_track_index,
                    file_path=str(path),
                    start_ms=0,
                    length_ms=length_ms
                )
                self.current_project.clips.append(new_clip)

                duration_sec = max(10, int(total_length_sec / len(structure)))
                section_snapshots.append({
                    "section_index": section_index,
                    "section_name": section_name,
                    "clip_id": self.next_clip_id,
                    "track_index": new_track_index,
                    "duration_seconds": duration_sec,
                    "lyrics": "",
                    "version": 1,
                })

                self.next_clip_id += 1

            self.last_song_generation = {
                "project_id": project_id,
                "structure": structure,
                "key": key,
                "chords": chords,
                "time_signature": time_sig,
                "tempo": tempo,
                "style": style,
                "genre": genre,
                "mood": mood,
                "use_cloud": use_cloud,
                "sections": section_snapshots,
            }
            self._persist_song_generation_metadata()
            self.refresh_alter_section_selector()

            self.sync_project_tracks_to_recording_engine()
            self.refresh_track_list()
            self.refresh_timeline()
            self.update_status("Full song generated with local audio clips.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate full song:\n{e}")

    def _find_clip_by_id(self, clip_id: int) -> Optional[Clip]:
        for clip in self.current_project.clips:
            if clip.id == clip_id:
                return clip
        return None

    def alter_generated_song_section(self):
        if not self.last_song_generation:
            QMessageBox.warning(
                self,
                "Alter section",
                "Generate a full song first, then alter a section by index."
            )
            return

        try:
            section_index = int(self.alter_section_index_input.text())
        except ValueError:
            QMessageBox.warning(self, "Input error", "Section index must be a number (0, 1, 2, ...).")
            return

        sections = self.last_song_generation["sections"]
        if section_index < 0 or section_index >= len(sections):
            QMessageBox.warning(self, "Input error", "Section index is out of range for the last generated song.")
            return

        section_data = sections[section_index]
        clip = self._find_clip_by_id(section_data["clip_id"])
        if clip is None:
            QMessageBox.warning(
                self,
                "Alter section",
                "Could not find the original clip for this section."
            )
            return

        override_lyrics = self.alter_section_lyrics_input.text().strip()
        lyrics = override_lyrics if override_lyrics else section_data["lyrics"]

        style = self.gen_style.text().strip() or self.last_song_generation["style"]
        genre = self.gen_genre.text().strip() or self.last_song_generation["genre"]
        mood = self.gen_mood.text().strip() or self.last_song_generation["mood"]

        next_version = section_data["version"] + 1
        section_name = section_data["section_name"]
        versioned_name = f"{section_name}_v{next_version}"

        try:
            result = generate_music_clip(
                style=style,
                genre=genre,
                mood=mood,
                lyrics=lyrics,
                duration_seconds=section_data["duration_seconds"],
                key=self.last_song_generation["key"],
                chords=self.last_song_generation["chords"],
                time_signature=self.last_song_generation["time_signature"],
                tempo_bpm=self.last_song_generation["tempo"],
                section_name=versioned_name,
                seed=None,
                project_id=self.last_song_generation["project_id"],
                use_cloud=self.last_song_generation["use_cloud"],
            )

            clip.file_path = str(result.audio_path)
            clip.length_ms = get_audio_length_ms(str(result.audio_path))

            section_data["version"] = next_version
            section_data["lyrics"] = lyrics
            self._persist_song_generation_metadata()
            self.refresh_alter_section_selector()

            self.refresh_timeline()
            self.update_status(f"Altered section {section_index} ({section_name}) without full regeneration")
            QMessageBox.information(
                self,
                "Section altered",
                f"Section {section_index} ({section_name}) was regenerated and replaced in-place."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to alter section:\n{e}")


# ── LIVE APPLICATION WINDOW ─────────────────────────────────────────────────────
# TabbedEchoProWindow is the concrete class created at startup.
# It extends EchoProWindow with the tabbed-strip layout.
class TabbedEchoProWindow(EchoProWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.setWindowTitle("Echo Pro")
        self.setMinimumSize(1100, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(DARK_STYLE)

        self._initialize_shared_window_state()
        self.mixer_rows = []

        # Initialize Group 2.1: TimelineSyncController (single source of truth for timeline state)
        self.timeline_controller = TimelineSyncController()

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self._setup_status_bar_widgets()

        self._initialize_shared_window_timers(start_recording_timer=False)

        self._build_ui()
        self._register_global_shortcuts()
        self.update_status("Starting Echo Pro...")
        QTimer.singleShot(0, self._finish_startup)

    def _finish_startup(self) -> None:
        self.recording_timer.start()
        self.refresh_track_list()
        self.refresh_audio_device_selectors()
        self.sync_project_tracks_to_recording_engine()
        self.sync_recording_controls_from_controller()
        self._build_recording_meters()
        self._rebuild_mixer_rows()
        self._apply_take_review_preferences()
        self.refresh_take_track_selector()
        self.refresh_take_review_list()
        self.refresh_alter_section_selector()
        self.update_recording_status_label()
        self._prompt_recovery_for_current_session()
        self.refresh_recovery_history()
        self.refresh_timeline()
        self._update_timeline_zoom_readout()
        self._refresh_status_bar_telemetry()
        self._refresh_application_state_machine()
        self.update_status("Ready")

    def _build_ui(self) -> None:
        build_ui(self)

    def _wrap_scroll(self, content: QWidget) -> QScrollArea:
        return wrap_scroll(self, content)

    def _ensure_single_track_editor_tab(self) -> QWidget:
        if self._single_track_editor_tab is not None:
            return self._single_track_editor_tab

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.single_track_editor_title = QLabel("Single Track Editor")
        self.single_track_editor_title.setStyleSheet("font-size:14px; font-weight:bold; color:#E2E2E5;")
        layout.addWidget(self.single_track_editor_title)

        self.single_track_editor_summary = QLabel("Double-click a waveform clip to focus a track.")
        self.single_track_editor_summary.setWordWrap(True)
        self.single_track_editor_summary.setStyleSheet("color:#aab4be;")
        layout.addWidget(self.single_track_editor_summary)

        self.single_track_editor_clip_list = QListWidget()
        self.single_track_editor_clip_list.setToolTip("Clips on the focused track")
        layout.addWidget(self.single_track_editor_clip_list, stretch=1)

        action_row = QHBoxLayout()
        jump_btn = QPushButton("Jump To First Clip")
        jump_btn.clicked.connect(self._single_track_editor_jump_to_first_clip)
        action_row.addWidget(jump_btn)

        playback_btn = QPushButton("Playback Settings…")
        playback_btn.clicked.connect(self._single_track_editor_open_playback_settings)
        action_row.addWidget(playback_btn)

        close_btn = QPushButton("Close Editor")
        close_btn.clicked.connect(self._close_single_track_editor)
        action_row.addWidget(close_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        self._single_track_editor_tab = tab
        return tab

    def _refresh_single_track_editor(self) -> None:
        if self._single_track_editor_tab is None:
            return
        track_index = self._single_track_editor_track_index
        if track_index is None or not (0 <= int(track_index) < len(self.current_project.tracks)):
            self.single_track_editor_title.setText("Single Track Editor")
            self.single_track_editor_summary.setText("Double-click a waveform clip to focus a track.")
            self.single_track_editor_clip_list.clear()
            return

        track = self.current_project.tracks[int(track_index)]
        clips = [clip for clip in self.current_project.clips if int(clip.track_index) == int(track_index)]
        clips.sort(key=lambda clip: int(clip.start_ms))
        self.single_track_editor_title.setText(f"Single Track Editor - Track {int(track_index) + 1}: {track.name}")
        self.single_track_editor_summary.setText(
            f"Track type: {getattr(track, 'track_type', 'Audio')} | Clips: {len(clips)} | "
            "This surface is track-focused and does not modify other tracks."
        )
        self.single_track_editor_clip_list.clear()
        for clip in clips:
            fade_in_ms = int((getattr(clip, "metadata", {}) or {}).get("fade_in_ms", 0) or 0)
            fade_out_ms = int((getattr(clip, "metadata", {}) or {}).get("fade_out_ms", 0) or 0)
            clip_name = str((getattr(clip, "metadata", {}) or {}).get("display_name", "")).strip() or Path(clip.file_path).name
            self.single_track_editor_clip_list.addItem(
                f"Clip {int(clip.id)} | {clip_name} | Start {int(clip.start_ms)}ms | Len {int(clip.length_ms)}ms | FadeIn {fade_in_ms}ms | FadeOut {fade_out_ms}ms"
            )

    def open_single_track_editor(self, track_index: int) -> None:
        if not (0 <= int(track_index) < len(self.current_project.tracks)):
            return
        tab = self._ensure_single_track_editor_tab()
        tab_index = self.tabs.indexOf(tab)
        if tab_index < 0:
            tab_index = self.tabs.addTab(tab, "Track Editor")
        self._single_track_editor_track_index = int(track_index)
        self._refresh_single_track_editor()
        self.tabs.setCurrentIndex(tab_index)
        self.update_status(f"Opened Track Editor for track {int(track_index) + 1}")

    def _close_single_track_editor(self) -> None:
        if self._single_track_editor_tab is None:
            return
        tab_index = self.tabs.indexOf(self._single_track_editor_tab)
        if tab_index >= 0:
            self.tabs.removeTab(tab_index)
        self._single_track_editor_track_index = None

    def _single_track_editor_open_playback_settings(self) -> None:
        track_index = self._single_track_editor_track_index
        if track_index is None:
            return
        self._open_track_playback_settings(int(track_index))
        self._refresh_single_track_editor()

    def _single_track_editor_jump_to_first_clip(self) -> None:
        track_index = self._single_track_editor_track_index
        if track_index is None:
            return
        clips = [clip for clip in self.current_project.clips if int(clip.track_index) == int(track_index)]
        if not clips:
            QMessageBox.information(self, "Track Editor", "This track has no clips yet.")
            return
        first_clip = min(clips, key=lambda clip: int(clip.start_ms))
        self._set_project_playhead_ms(int(first_clip.start_ms))
        self._switch_to_tab("Home")
        self.update_status(f"Playhead moved to first clip on track {int(track_index) + 1}")

    def _build_overview_tab(self) -> QWidget:
        return build_overview_tab(self)

    def _on_timeline_add_clip_at(self, track_index: int, start_ms: int) -> None:
        on_timeline_add_clip_at(self, track_index, start_ms)

    def add_clip_from_browser_path(self, file_path: Path, *, create_new_track: bool = False) -> bool:
        """Add an audio file selected from the mixer Browser sidebar into the project."""
        path = Path(file_path)
        if not path.exists():
            QMessageBox.warning(self, "Browser Add", "Selected browser file no longer exists.")
            return False

        target_track_index = self.selected_track_index
        should_create_track = bool(create_new_track or target_track_index is None or target_track_index < 0 or target_track_index >= len(self.current_project.tracks))
        if should_create_track:
            self._mark_project_edit("Add browser clip to new track")
            self._add_track_with_type("Audio", capture_history=False)
            target_track_index = len(self.current_project.tracks) - 1
        else:
            self._mark_project_edit(f"Add browser clip to track {int(target_track_index) + 1}")

        try:
            length_ms = get_audio_length_ms(str(path))
            start_ms = max(0, int(self.project_playhead_ms))
            clip = Clip(
                id=self.next_clip_id,
                track_index=int(target_track_index),
                file_path=str(path),
                start_ms=start_ms,
                length_ms=length_ms,
            )
            self.current_project.clips.append(clip)
            self.next_clip_id += 1
            self.refresh_timeline()
            self.update_status(
                f"Added clip from Browser to track {int(target_track_index) + 1} at {start_ms / 1000.0:.2f}s: {path.name}"
            )
            return True
        except Exception as e:
            QMessageBox.critical(self, "Browser Add", f"Failed to add browser clip:\n{e}")
            return False

    def _handle_timeline_clip_action(self, action: str, clip_id: int) -> None:
        clip = next((item for item in self.current_project.clips if int(item.id) == int(clip_id)), None)
        if clip is None:
            self.update_status("Clip action ignored: clip no longer exists")
            return

        if action == "duplicate":
            self._mark_project_edit(f"Duplicate clip {clip_id}")
            duplicated = Clip(
                id=self.next_clip_id,
                track_index=int(clip.track_index),
                file_path=str(clip.file_path),
                start_ms=int(clip.start_ms) + 250,
                length_ms=int(clip.length_ms),
                metadata=dict(getattr(clip, "metadata", {}) or {}),
            )
            self.current_project.clips.append(duplicated)
            self.next_clip_id += 1
            self.refresh_timeline()
            self.update_status(f"Duplicated clip {clip_id} to clip {duplicated.id}")
            return

        if action == "demucs":
            self.stem_source_input.setText(str(clip.file_path))
            self._refresh_stem_section_state()
            self._switch_to_tab("Tools")
            self.update_status(f"Loaded clip {clip_id} into Demucs source")
            return

        if action == "ace_step":
            self._switch_to_tab("AI Generation (ACE-Step)")
            if hasattr(self, "ace_audio_reference_source_combo"):
                self.ace_audio_reference_source_combo.setCurrentText("Last Demucs Stem")
            if hasattr(self, "ace_audio_reference_thumbnail"):
                self.ace_audio_reference_thumbnail.setText(f"Reference: {Path(clip.file_path).name}")
            if hasattr(self, "ace_prompt_input"):
                self.ace_prompt_input.setPlainText(f"Use {Path(clip.file_path).name} as a creative reference for a new ACE-Step generation.")
            self.update_status(f"Switched to ACE-Step tab for clip {clip_id}")
            return

        if action == "rename":
            current_name = str((getattr(clip, "metadata", {}) or {}).get("display_name", "")).strip() or Path(clip.file_path).name
            new_name, accepted = QInputDialog.getText(self, "Rename Clip", "Clip name", text=current_name)
            if not accepted:
                return
            cleaned_name = str(new_name).strip()
            if not cleaned_name:
                QMessageBox.warning(self, "Rename Clip", "Clip name cannot be empty.")
                return
            metadata = dict(getattr(clip, "metadata", {}) or {})
            self._mark_project_edit(f"Rename clip {clip_id}")
            metadata["display_name"] = cleaned_name
            clip.metadata = metadata
            self.refresh_timeline()
            self.update_status(f"Renamed clip {clip_id} to {cleaned_name}")
            return

        if action == "export":
            source_path = Path(clip.file_path)
            if not source_path.exists():
                QMessageBox.warning(self, "Export Clip", "Source clip file is missing on disk.")
                return

            clip_name = str((getattr(clip, "metadata", {}) or {}).get("display_name", "")).strip() or source_path.stem
            default_suffix = source_path.suffix or ".wav"
            default_name = f"{clip_name}{default_suffix}"
            target_path_str, _ = QFileDialog.getSaveFileName(
                self,
                "Export Clip",
                str(source_path.with_name(default_name)),
                "Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)",
            )
            if not target_path_str:
                return

            target_path = Path(target_path_str)
            if target_path.resolve() == source_path.resolve():
                QMessageBox.information(self, "Export Clip", "Source and target are the same file. Choose a different path.")
                return

            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)
            except Exception as error:
                QMessageBox.critical(self, "Export Clip", f"Failed to export clip:\n{error}")
                return

            self.update_status(f"Exported clip {clip_id} to {target_path.name}")
            return

        if action == "properties":
            pre_change_snapshot = self._snapshot_project_edit_state()
            previous_name = str((getattr(clip, "metadata", {}) or {}).get("display_name", "")).strip() or Path(clip.file_path).name
            renamed = self._show_clip_properties_dialog(clip)
            if renamed:
                current_name = str((getattr(clip, "metadata", {}) or {}).get("display_name", "")).strip() or Path(clip.file_path).name
                if current_name != previous_name:
                    self._push_project_snapshot(f"Edit clip {clip_id} properties", pre_change_snapshot)
                self.refresh_timeline()
                clip_name = str((getattr(clip, "metadata", {}) or {}).get("display_name", "")).strip() or Path(clip.file_path).name
                self.update_status(f"Updated properties for clip {clip_id}: {clip_name}")
            else:
                self.update_status(f"Displayed properties for clip {clip_id}")
            return

        if action == "fade_settings":
            self._show_clip_fade_settings_popover(int(clip_id))
            self.update_status(f"Opened fade settings for clip {clip_id}")
            return

    def _show_clip_properties_dialog(self, clip: Clip) -> bool:
        source_path = Path(clip.file_path)
        metadata = dict(getattr(clip, "metadata", {}) or {})
        current_name = str(metadata.get("display_name", "")).strip() or source_path.name
        track_index = int(clip.track_index)
        track_name = self.current_project.tracks[track_index].name if 0 <= track_index < len(self.current_project.tracks) else f"Track {track_index}"
        start_sec = float(int(clip.start_ms)) / 1000.0
        length_sec = float(max(0, int(clip.length_ms))) / 1000.0
        file_size_text = "unknown"
        if source_path.exists():
            try:
                file_size_text = f"{source_path.stat().st_size:,} bytes"
            except OSError:
                file_size_text = "unavailable"
        metadata_keys = ", ".join(sorted(metadata.keys())) or "none"

        dialog = QDialog(self)
        dialog.setWindowTitle("Clip Properties")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        name_input = QLineEdit(current_name)
        name_input.selectAll()
        form.addRow("Name", name_input)
        form.addRow("Source file", QLabel(source_path.name))
        form.addRow("Path", QLabel(str(source_path)))
        form.addRow("Track", QLabel(f"{track_name} ({track_index})"))
        form.addRow("Start", QLabel(f"{start_sec:.2f}s"))
        form.addRow("Length", QLabel(f"{length_sec:.2f}s"))
        form.addRow("File size", QLabel(file_size_text))
        form.addRow("Metadata keys", QLabel(metadata_keys))
        layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)

        def _accept_if_valid() -> None:
            if not name_input.text().strip():
                QMessageBox.warning(dialog, "Clip Properties", "Clip name cannot be empty.")
                return
            dialog.accept()

        button_box.accepted.connect(_accept_if_valid)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() != QDialog.Accepted:
            return False

        new_name = name_input.text().strip()
        previous_name = str(metadata.get("display_name", "")).strip() or source_path.name
        if new_name == previous_name:
            return False
        metadata["display_name"] = new_name
        clip.metadata = metadata
        return True

    def _switch_to_tab(self, tab_name: str) -> None:
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == tab_name:
                self.tabs.setCurrentIndex(index)
                return

    def _should_ignore_shortcut_while_typing(self) -> bool:
        focused = QApplication.focusWidget()
        if focused is None:
            return False
        if isinstance(focused, QLineEdit):
            return True
        if isinstance(focused, (QTextEdit, QPlainTextEdit, QAbstractSpinBox)):
            return True
        if isinstance(focused, QComboBox) and focused.isEditable():
            return True
        return False

    def _activate_shortcut_action(self, action_name: str) -> None:
        if action_name == "Play/Stop":
            if self._should_ignore_shortcut_while_typing():
                return
            if self._is_project_playback_running() or is_playback_active():
                self.stop_current_project_playback()
            else:
                self.play_current_project()
            return

        if action_name == "Record":
            if self._should_ignore_shortcut_while_typing():
                return
            if self.recording_controller.status.is_recording or self.recording_controller.status.count_in_active:
                self.stop_recording_session()
            else:
                self.start_recording_session()
            return

        if action_name == "Jump To Start":
            self.jump_to_transport_start()
            return
        if action_name == "Jump To End":
            self.jump_to_transport_end()
            return
        if action_name == "Undo":
            if not self.undo_project_edit():
                self.update_status("Nothing to undo")
            return
        if action_name == "Redo":
            if not self.redo_project_edit():
                self.update_status("Nothing to redo")
            return
        if action_name == "Save Project":
            self.save_project_dialog()
            return
        if action_name == "Delete Clip":
            if self._should_ignore_shortcut_while_typing():
                return
            self.delete_selected_timeline_clip()
            return
        if action_name == "Split At Playhead":
            if self._should_ignore_shortcut_while_typing():
                return
            self.split_selected_clip_at_playhead()
            return
        if action_name == "New Track":
            self.add_track()
            return
        if action_name == "Mute Track":
            if self._should_ignore_shortcut_while_typing():
                return
            self.toggle_selected_track_mute()
            return
        if action_name == "Solo Track":
            self.toggle_selected_track_solo()
            return
        if action_name == "Open Stem Separation":
            self._switch_to_tab("Stem Separation")
            self.update_status("Opened Stem Separation tab")
            return
        if action_name == "Open ACE-Step":
            self._switch_to_tab("AI Generation (ACE-Step)")
            self.update_status("Opened ACE-Step tab")
            return
        if action_name == "Open Mastering":
            self._switch_to_tab("Mastering")
            self.update_status("Opened Mastering tab")
            return
        if action_name == "MIDI Learn Mode":
            self._switch_to_tab("MIDI Mapping")
            if hasattr(self, "midi_learn_toggle_btn"):
                self.midi_learn_toggle_btn.toggle()
            else:
                self._toggle_midi_learn_mode(not bool(self._midi_learn_active))
            self.update_status("Toggled MIDI Learn mode")
            return
        if action_name == "New Project":
            self.new_project()
            return
        if action_name == "Open Project":
            self.open_project()
            return
        if action_name == "Export":
            self.export_project_mix_dialog()
            return

    def _register_global_shortcuts(self) -> None:
        for shortcut in self._global_shortcuts:
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        self._global_shortcuts = []

        self._initialize_settings_state()
        shortcut_map = self._default_settings_shortcuts()
        if self._settings_state is not None:
            configured = self._settings_state.get("shortcuts")
            if isinstance(configured, dict):
                shortcut_map.update({str(key): str(value) for key, value in configured.items()})

        action_order = [
            "Play/Stop",
            "Record",
            "Jump To Start",
            "Jump To End",
            "Undo",
            "Redo",
            "Save Project",
            "Delete Clip",
            "Split At Playhead",
            "New Track",
            "Mute Track",
            "Solo Track",
            "Open Stem Separation",
            "Open ACE-Step",
            "Open Mastering",
            "MIDI Learn Mode",
            "New Project",
            "Open Project",
            "Export",
        ]

        for action_name in action_order:
            keybind = str(shortcut_map.get(action_name, "")).strip()
            if not keybind:
                continue
            sequence = QKeySequence(keybind)
            if sequence.isEmpty():
                continue
            shortcut = QShortcut(sequence, self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(lambda action=action_name: self._activate_shortcut_action(action))
            self._global_shortcuts.append(shortcut)

        next_tab_shortcut = QShortcut(QKeySequence("Ctrl+Tab"), self)
        next_tab_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        next_tab_shortcut.activated.connect(self._select_next_tab)
        self._global_shortcuts.append(next_tab_shortcut)

        prev_tab_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Tab"), self)
        prev_tab_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        prev_tab_shortcut.activated.connect(self._select_previous_tab)
        self._global_shortcuts.append(prev_tab_shortcut)

    def _select_next_tab(self) -> None:
        if not hasattr(self, "tabs") or self.tabs.count() <= 0:
            return
        self.tabs.setCurrentIndex((int(self.tabs.currentIndex()) + 1) % int(self.tabs.count()))

    def _select_previous_tab(self) -> None:
        if not hasattr(self, "tabs") or self.tabs.count() <= 0:
            return
        self.tabs.setCurrentIndex((int(self.tabs.currentIndex()) - 1) % int(self.tabs.count()))



    def _build_recording_tab(self) -> QWidget:
        return build_recording_tab(self)

    def _build_voice_tab(self) -> QWidget:
        return build_voice_tab(self)

    def _populate_voice_profile_combo(self) -> None:
        populate_voice_profile_combo(self)

    def _add_custom_ace_lora(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Add Custom LoRA",
            str(ACE_MODELS_DIR),
            "LoRA / checkpoint files (*.safetensors *.ckpt *.pt);;All Files (*)",
        )
        if not file_path:
            return
        display = Path(file_path).stem
        if hasattr(self, "ace_lora_combo"):
            existing = self.ace_lora_combo.findData(file_path)
            if existing < 0:
                self.ace_lora_combo.addItem(display, file_path)
            self.ace_lora_combo.setCurrentText(display)
        self.update_status(f"Added ACE-Step LoRA: {display}")

    def _build_ace_step_tab(self) -> QWidget:
        return build_ace_step_tab(self)

    def _build_mastering_chain_tab(self) -> QWidget:
        return build_mastering_chain_tab(self, EqCurvePreviewWidget, LufsHistoryWidget)

    def _build_midi_mapping_tab(self) -> QWidget:
        return build_midi_mapping_tab(self)

    def _on_mastering_target_changed(self, preset_name: str) -> None:
        state = self._mastering_chain_state()
        state["lufs_target_preset"] = str(preset_name)
        state["lufs_target_db"] = self._mastering_preset_to_target_db(preset_name)
        self._master_lufs_target_preset = str(preset_name)
        self._master_lufs_target_db = float(state["lufs_target_db"])
        self._save_mastering_chain_state(state)
        self._refresh_mastering_chain_page()

    def _on_mastering_input_trim_changed(self, value: int) -> None:
        state = self._mastering_chain_state()
        state["input_trim_db"] = int(value)
        self._save_mastering_chain_state(state)
        self._refresh_mastering_chain_page()

    def _on_mastering_eq_band_changed(self, band_index: int, value: int) -> None:
        state = self._mastering_chain_state()
        bands = [
            float(state.get("eq_low_gain_db", 0.0)),
            float(state.get("eq_low_mid_gain_db", 0.0)),
            float(state.get("eq_high_mid_gain_db", 0.0)),
            float(state.get("eq_high_gain_db", 0.0)),
        ]
        if 0 <= band_index < len(bands):
            bands[band_index] = float(value)
        state["eq_low_gain_db"], state["eq_low_mid_gain_db"], state["eq_high_mid_gain_db"], state["eq_high_gain_db"] = bands
        self._save_mastering_chain_state(state)
        self._refresh_mastering_chain_page()

    def _on_mastering_compressor_changed(self, key: str, value) -> None:
        state = self._mastering_chain_state()
        state[str(key)] = value
        self._save_mastering_chain_state(state)
        self._refresh_mastering_chain_page()

    def _on_mastering_widener_changed(self, value: int) -> None:
        state = self._mastering_chain_state()
        state["widener_width_pct"] = int(value)
        self._save_mastering_chain_state(state)
        self._refresh_mastering_chain_page()

    def _on_mastering_limiter_changed(self, key: str, value) -> None:
        state = self._mastering_chain_state()
        state[str(key)] = value
        self._save_mastering_chain_state(state)
        self._refresh_mastering_chain_page()

    def _refresh_mastering_chain_page(self) -> None:
        if not hasattr(self, "master_lufs_chart"):
            return

        state = self._mastering_chain_state()
        current_lufs = max(-70.0, min(3.0, float(self._project_playback_lufs_integrated_db) - 0.8))

        self._master_lufs_history.append(float(current_lufs))
        self._master_lufs_history = self._master_lufs_history[-180:]

        short_term = max(-70.0, min(3.0, float(self._master_short_term_lufs_db)))
        momentary = max(-70.0, min(3.0, float(self._master_momentary_lufs_db)))
        lra = max(0.0, min(24.0, float(self._master_lufs_range_db)))
        true_peak = max(-80.0, min(6.0, float(self._master_true_peak_db)))

        target_db = float(state.get("lufs_target_db", -14.0))
        if current_lufs <= (target_db - 2.0):
            integrated_color = "#7fe0b5"
        elif current_lufs <= (target_db + 1.5):
            integrated_color = "#f2b84b"
        else:
            integrated_color = "#f36f9f"

        if hasattr(self, "mastering_target_combo"):
            self.mastering_target_combo.blockSignals(True)
            self.mastering_target_combo.setCurrentText(str(state.get("lufs_target_preset", "Spotify -14")))
            self.mastering_target_combo.blockSignals(False)

        if hasattr(self, "master_input_trim_slider"):
            self.master_input_trim_slider.blockSignals(True)
            self.master_input_trim_slider.setValue(int(state.get("input_trim_db", 0)))
            self.master_input_trim_slider.blockSignals(False)
            self.master_input_trim_value.setText(f"{int(state.get('input_trim_db', 0)):+d} dB")
        if hasattr(self, "master_input_trim_bypass"):
            self.master_input_trim_bypass.blockSignals(True)
            self.master_input_trim_bypass.setChecked(bool(state.get("input_trim_bypassed", False)))
            self.master_input_trim_bypass.blockSignals(False)

        eq_values = [
            int(round(float(state.get("eq_low_gain_db", 0.0)))),
            int(round(float(state.get("eq_low_mid_gain_db", 0.0)))),
            int(round(float(state.get("eq_high_mid_gain_db", 0.0)))),
            int(round(float(state.get("eq_high_gain_db", 0.0)))),
        ]
        for slider, value in [
            (self.master_eq_low_slider, eq_values[0]),
            (self.master_eq_low_mid_slider, eq_values[1]),
            (self.master_eq_high_mid_slider, eq_values[2]),
            (self.master_eq_high_slider, eq_values[3]),
        ]:
            slider.blockSignals(True)
            slider.setValue(int(value))
            slider.blockSignals(False)
        self.master_eq_curve.set_bands([float(value) for value in eq_values])
        if hasattr(self, "master_eq_bypass"):
            self.master_eq_bypass.blockSignals(True)
            self.master_eq_bypass.setChecked(bool(state.get("eq_bypassed", False)))
            self.master_eq_bypass.blockSignals(False)

        for widget, key in [
            (self.master_comp_threshold, "compressor_threshold_db"),
            (self.master_comp_ratio, "compressor_ratio"),
            (self.master_comp_attack, "compressor_attack_ms"),
            (self.master_comp_release, "compressor_release_ms"),
            (self.master_comp_knee, "compressor_knee_db"),
            (self.master_comp_makeup, "compressor_makeup_db"),
        ]:
            widget.blockSignals(True)
            widget.setValue(type(widget.value())(state.get(key, widget.value())))
            widget.blockSignals(False)
        if hasattr(self, "master_comp_bypass"):
            self.master_comp_bypass.blockSignals(True)
            self.master_comp_bypass.setChecked(bool(state.get("compressor_bypassed", False)))
            self.master_comp_bypass.blockSignals(False)

        if hasattr(self, "master_comp_input_vu") and hasattr(self, "master_comp_gr_vu"):
            vu_input_pct = int(round(max(0.0, min(100.0, ((current_lufs + 70.0) / 73.0) * 100.0))))
            threshold_db = float(state.get("compressor_threshold_db", -12.0))
            ratio = max(1.0, float(state.get("compressor_ratio", 2.0)))
            above_threshold_db = max(0.0, float(momentary) - threshold_db)
            gain_reduction_db = max(0.0, min(24.0, above_threshold_db * (1.0 - (1.0 / ratio))))
            gain_reduction_pct = int(round((gain_reduction_db / 24.0) * 100.0))
            self.master_comp_input_vu.setValue(vu_input_pct)
            self.master_comp_gr_vu.setValue(gain_reduction_pct)
            self.master_comp_input_vu_label.setText(f"Input: {current_lufs:+.1f} LUFS")
            self.master_comp_gr_label.setText(f"GR: {gain_reduction_db:.1f} dB")

        self.master_widener_slider.blockSignals(True)
        self.master_widener_slider.setValue(int(state.get("widener_width_pct", 100)))
        self.master_widener_slider.blockSignals(False)
        self.master_widener_value.setText(f"{int(state.get('widener_width_pct', 100))}%")
        if hasattr(self, "master_widener_bypass"):
            self.master_widener_bypass.blockSignals(True)
            self.master_widener_bypass.setChecked(bool(state.get("widener_bypassed", False)))
            self.master_widener_bypass.blockSignals(False)

        self.master_limiter_threshold_slider.blockSignals(True)
        self.master_limiter_threshold_slider.setValue(int(state.get("limiter_threshold_db", -3)))
        self.master_limiter_threshold_slider.blockSignals(False)
        self.master_limiter_threshold_value.setText(f"{int(state.get('limiter_threshold_db', -3))} dB")

        self.master_limiter_ceiling_slider.blockSignals(True)
        self.master_limiter_ceiling_slider.setValue(int(state.get("limiter_ceiling_db", -1)))
        self.master_limiter_ceiling_slider.blockSignals(False)
        self.master_limiter_ceiling_value.setText(f"{int(state.get('limiter_ceiling_db', -1))} dB")

        self.master_limiter_release.blockSignals(True)
        self.master_limiter_release.setValue(int(state.get("limiter_release_ms", 80)))
        self.master_limiter_release.blockSignals(False)
        if hasattr(self, "master_limiter_bypass"):
            self.master_limiter_bypass.blockSignals(True)
            self.master_limiter_bypass.setChecked(bool(state.get("limiter_bypassed", False)))
            self.master_limiter_bypass.blockSignals(False)

        if hasattr(self, "master_limiter_clip_label"):
            self.master_limiter_clip_label.setText("Clip LED: hot" if true_peak > 0.0 else "Clip LED: idle")
            self.master_limiter_true_peak_label.setText(f"True peak: {true_peak:+.1f} dBTP")

        if hasattr(self, "master_output_bypass"):
            self.master_output_bypass.blockSignals(True)
            self.master_output_bypass.setChecked(bool(state.get("output_bypassed", False)))
            self.master_output_bypass.blockSignals(False)

        self.master_output_target_label.setText(f"Target: {state.get('lufs_target_preset', 'Spotify -14')}")
        self.master_output_integrated_label.setText(f"Integrated: {current_lufs:+.1f} LUFS-I")
        self.master_output_short_term_label.setText(f"Short-term: {short_term:+.1f} LUFS-S")
        self.master_output_momentary_label.setText(f"Momentary: {momentary:+.1f} LUFS-M")
        self.master_output_lra_label.setText(f"LU Range: {lra:.1f} LU")

        self.master_lufs_integrated_label.setText(f"{current_lufs:+.1f} LUFS-I")
        self.master_lufs_short_term_label.setText(f"{short_term:+.1f} LUFS-S")
        self.master_lufs_momentary_label.setText(f"{momentary:+.1f} LUFS-M")
        self.master_lufs_range_label.setText(f"{lra:.1f} LU")
        self.master_lufs_true_peak_label.setText(f"{true_peak:+.1f} dBTP")
        self.master_lufs_integrated_label.setStyleSheet(f"color:{integrated_color}; font-family:Consolas, monospace; font-size:13px;")
        self.master_lufs_chart.set_values(self._master_lufs_history, target_db, current_lufs)
        self.master_lufs_target_value.setText(f"Target: {state.get('lufs_target_preset', 'Spotify -14')} ({target_db:+.1f} LUFS-I)")

    def _build_music_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        gen_group = QGroupBox("Music Generator")
        gen_layout = QGridLayout(gen_group)
        self.gen_style = QLineEdit()
        self.gen_style.setToolTip("Musical style (e.g. lofi, cinematic, chill)")
        self.gen_genre = QLineEdit()
        self.gen_genre.setToolTip("Genre (e.g. rock, EDM, orchestral, jazz)")
        self.gen_mood = QLineEdit()
        self.gen_mood.setToolTip("Mood or energy (e.g. calm, energetic, melancholic)")
        self.gen_lyrics = QLineEdit()
        self.gen_lyrics.setToolTip("Optional lyrics snippet to guide generation")
        self.gen_duration = QLineEdit()
        self.gen_duration.setToolTip("Duration in seconds (10–300)")
        self.cloud_enabled = QLineEdit("no")
        self.cloud_enabled.setToolTip("Type 'yes' to use the cloud backend; 'no' for local ACE Step 1.5")
        gen_layout.addWidget(QLabel("Style"), 0, 0)
        gen_layout.addWidget(self.gen_style, 0, 1)
        gen_layout.addWidget(QLabel("Genre"), 0, 2)
        gen_layout.addWidget(self.gen_genre, 0, 3)
        gen_layout.addWidget(QLabel("Mood"), 1, 0)
        gen_layout.addWidget(self.gen_mood, 1, 1)
        gen_layout.addWidget(QLabel("Lyrics"), 1, 2)
        gen_layout.addWidget(self.gen_lyrics, 1, 3)
        gen_layout.addWidget(QLabel("Duration"), 2, 0)
        gen_layout.addWidget(self.gen_duration, 2, 1)
        gen_layout.addWidget(QLabel("Cloud"), 2, 2)
        gen_layout.addWidget(self.cloud_enabled, 2, 3)
        gen_btn = QPushButton("Generate Clip")
        gen_btn.setToolTip("Generate a single music clip with the specified parameters")
        gen_btn.clicked.connect(self.generate_single_clip)
        gen_layout.addWidget(gen_btn, 2, 4)
        layout.addWidget(gen_group)

        plan_group = QGroupBox("Song Planner")
        plan_layout = QGridLayout(plan_group)
        self.plan_total_length = QLineEdit()
        self.plan_total_length.setToolTip("Total song duration in seconds")
        self.plan_structure = QLineEdit()
        self.plan_structure.setToolTip("Comma-separated song sections, e.g. Intro,Verse,Chorus,Bridge,Outro")
        self.plan_key = QLineEdit()
        self.plan_key.setToolTip("Musical key, e.g. C major, A minor")
        self.plan_chords = QLineEdit()
        self.plan_chords.setToolTip("Chord progression, e.g. C-G-Am-F")
        self.plan_time_sig = QLineEdit()
        self.plan_time_sig.setToolTip("Time signature, e.g. 4/4, 3/4, 6/8")
        self.plan_tempo = QLineEdit()
        self.plan_tempo.setToolTip("Tempo in beats per minute (BPM)")
        self.plan_lyrics = QTextEdit()
        self.plan_lyrics.setToolTip("Full lyrics for the song — used to match sections")
        plan_layout.addWidget(QLabel("Total Length"), 0, 0)
        plan_layout.addWidget(self.plan_total_length, 0, 1)
        plan_layout.addWidget(QLabel("Structure"), 0, 2)
        plan_layout.addWidget(self.plan_structure, 0, 3)
        plan_layout.addWidget(QLabel("Key"), 1, 0)
        plan_layout.addWidget(self.plan_key, 1, 1)
        plan_layout.addWidget(QLabel("Chords"), 1, 2)
        plan_layout.addWidget(self.plan_chords, 1, 3)
        plan_layout.addWidget(QLabel("Time Sig"), 2, 0)
        plan_layout.addWidget(self.plan_time_sig, 2, 1)
        plan_layout.addWidget(QLabel("Tempo"), 2, 2)
        plan_layout.addWidget(self.plan_tempo, 2, 3)
        plan_layout.addWidget(QLabel("Lyrics"), 3, 0)
        plan_layout.addWidget(self.plan_lyrics, 3, 1, 1, 3)
        plan_btn = QPushButton("Generate Full Song")
        plan_btn.setToolTip("Generate audio clips for all sections and add them to the project")
        plan_btn.clicked.connect(self.generate_full_song)
        plan_layout.addWidget(plan_btn, 4, 3)
        layout.addWidget(plan_group)

        alter_group = QGroupBox("Section Tweaks")
        alter_layout = QHBoxLayout(alter_group)
        self.alter_section_selector = QComboBox()
        self.alter_section_selector.setToolTip("Select a generated section to regenerate")
        self.alter_section_selector.currentIndexChanged.connect(self.on_alter_section_selector_changed)
        self.alter_section_index_input = QLineEdit()
        self.alter_section_index_input.setToolTip("Section index (auto-filled from the dropdown above)")
        self.alter_section_lyrics_input = QLineEdit()
        self.alter_section_lyrics_input.setToolTip("Optional replacement lyrics for just this section")
        alter_layout.addWidget(self.alter_section_selector)
        alter_layout.addWidget(self.alter_section_index_input)
        alter_layout.addWidget(self.alter_section_lyrics_input)
        alter_btn = QPushButton("Alter Section")
        alter_btn.setToolTip("Regenerate only the selected section without re-generating the whole song")
        alter_btn.clicked.connect(self.alter_generated_song_section)
        alter_layout.addWidget(alter_btn)
        layout.addWidget(alter_group)

        return tab

    def _build_tools_tab(self) -> QWidget:
        return build_tools_tab(self)

    def _build_demucs_tab(self) -> QWidget:
        return build_demucs_tab(self, StemSourceDropZone)

    def _build_settings_tab(self) -> QWidget:
        return build_settings_tab(self)

    def _default_midi_mapping_rows(self) -> list[dict]:
        return [
            {"category": "Transport", "parameter": "Play/Stop", "cc": 20, "channel": 0, "min": 0.0, "max": 1.0, "curve": "Linear", "current": 0.0},
            {"category": "Transport", "parameter": "Record", "cc": 21, "channel": 0, "min": 0.0, "max": 1.0, "curve": "Linear", "current": 0.0},
            {"category": "Mixer", "parameter": "Master Volume", "cc": 7, "channel": 0, "min": 0.0, "max": 1.0, "curve": "Linear", "current": 0.0},
            {"category": "Mixer", "parameter": "Selected Track Volume", "cc": 22, "channel": 0, "min": 0.0, "max": 1.0, "curve": "Linear", "current": 0.0},
            {"category": "Mixer", "parameter": "Selected Track Pan", "cc": 23, "channel": 0, "min": -1.0, "max": 1.0, "curve": "Linear", "current": 0.0},
            {"category": "AI", "parameter": "Stem/ACE Influence", "cc": 24, "channel": 0, "min": 0.0, "max": 1.0, "curve": "Log", "current": 0.0},
        ]

    def _initialize_midi_mapping_state(self) -> None:
        stored = self.current_project.metadata.get("midi_mapping_state")
        if isinstance(stored, dict):
            rows = stored.get("rows")
            if isinstance(rows, list):
                normalized_rows: list[dict] = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    normalized_rows.append(
                        {
                            "category": str(row.get("category", "MIDI")),
                            "parameter": str(row.get("parameter", "Parameter")),
                            "cc": int(row.get("cc", 0)),
                            "channel": int(row.get("channel", 0)),
                            "min": float(row.get("min", 0.0)),
                            "max": float(row.get("max", 1.0)),
                            "curve": str(row.get("curve", "Linear")),
                            "current": float(row.get("current", 0.0)),
                        }
                    )
                if normalized_rows:
                    self._midi_mapping_rows = normalized_rows
            filter_channel = stored.get("selected_channel")
            if isinstance(filter_channel, int) and hasattr(self, "midi_channel_combo"):
                idx = self.midi_channel_combo.findData(int(filter_channel))
                if idx >= 0:
                    self.midi_channel_combo.setCurrentIndex(idx)

        if not self._midi_mapping_rows:
            self._midi_mapping_rows = self._default_midi_mapping_rows()

    def _persist_midi_mapping_state(self) -> None:
        self.current_project.metadata["midi_mapping_state"] = {
            "rows": copy.deepcopy(self._midi_mapping_rows),
            "selected_channel": int(self.midi_channel_combo.currentData()) if hasattr(self, "midi_channel_combo") and isinstance(self.midi_channel_combo.currentData(), int) else -1,
        }
        self._refresh_status_bar_telemetry()

    def _append_midi_console(self, text: str) -> None:
        if not hasattr(self, "midi_console_view"):
            return
        timestamp = time.strftime("%H:%M:%S")
        self.midi_console_view.appendPlainText(f"[{timestamp}] {text}")
        cursor = self.midi_console_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.midi_console_view.setTextCursor(cursor)

    def _refresh_midi_mapping_table(self) -> None:
        if not hasattr(self, "midi_mapping_table"):
            return
        table = self.midi_mapping_table
        table.blockSignals(True)
        table.setRowCount(0)
        for row_idx, mapping in enumerate(self._midi_mapping_rows):
            table.insertRow(row_idx)
            label = f"{mapping['category']} / {mapping['parameter']}"
            item_label = QTableWidgetItem(label)
            item_label.setData(Qt.ItemDataRole.UserRole, row_idx)
            item_label.setFlags(item_label.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row_idx, 0, item_label)

            current_item = QTableWidgetItem(f"{float(mapping.get('current', 0.0)):.3f}")
            current_item.setFlags(current_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row_idx, 1, current_item)
            table.setItem(row_idx, 2, QTableWidgetItem(str(int(mapping.get("cc", 0)))))
            table.setItem(row_idx, 3, QTableWidgetItem(str(int(mapping.get("channel", 0)) + 1)))
            table.setItem(row_idx, 4, QTableWidgetItem(f"{float(mapping.get('min', 0.0)):.3f}"))
            table.setItem(row_idx, 5, QTableWidgetItem(f"{float(mapping.get('max', 1.0)):.3f}"))

            curve_combo = QComboBox()
            curve_combo.addItems(["Linear", "Log", "Exp"])
            curve_idx = curve_combo.findText(str(mapping.get("curve", "Linear")), Qt.MatchFlag.MatchFixedString)
            if curve_idx >= 0:
                curve_combo.setCurrentIndex(curve_idx)
            curve_combo.currentTextChanged.connect(lambda value, idx=row_idx: self._on_midi_curve_changed(idx, value))
            table.setCellWidget(row_idx, 6, curve_combo)

            learn_btn = QPushButton("Learn")
            learn_btn.clicked.connect(lambda _checked=False, idx=row_idx: self._set_midi_learn_target_row(idx))
            table.setCellWidget(row_idx, 7, learn_btn)
        table.blockSignals(False)

    def _set_midi_learn_target_row(self, row_index: int) -> None:
        if not (0 <= int(row_index) < len(self._midi_mapping_rows)):
            return
        self._midi_learn_pending_row = int(row_index)
        mapping = self._midi_mapping_rows[int(row_index)]
        self.midi_learn_confirmation_label.setText(
            f"Learning target: {mapping['category']} / {mapping['parameter']}"
        )
        self._append_midi_console(
            f"MIDI Learn target selected: {mapping['category']} / {mapping['parameter']}"
        )

    def _toggle_midi_learn_mode(self, enabled: bool) -> None:
        self._midi_learn_active = bool(enabled)
        if enabled:
            self.midi_learn_toggle_btn.setText("Disable MIDI Learn")
            self.midi_learn_banner.setText("MIDI Learn Active")
            self.midi_learn_banner.setStyleSheet("background:#6b4f1d; color:#ffdba8; padding:6px; border-radius:6px; font-weight:700;")
            self._append_midi_console("MIDI Learn enabled")
            self._refresh_application_state_machine()
            return
        self.midi_learn_toggle_btn.setText("Enable MIDI Learn")
        self.midi_learn_banner.setText("MIDI Learn Inactive")
        self.midi_learn_banner.setStyleSheet("background:#3a4553; color:#c9d5e2; padding:6px; border-radius:6px; font-weight:600;")
        self._append_midi_console("MIDI Learn disabled")
        self._refresh_application_state_machine()

    def _on_midi_curve_changed(self, row_index: int, value: str) -> None:
        if not (0 <= int(row_index) < len(self._midi_mapping_rows)):
            return
        self._midi_mapping_rows[int(row_index)]["curve"] = str(value)
        self._persist_midi_mapping_state()

    def _on_midi_mapping_item_changed(self, item: QTableWidgetItem) -> None:
        if item is None:
            return
        row = int(item.row())
        if not (0 <= row < len(self._midi_mapping_rows)):
            return
        mapping = self._midi_mapping_rows[row]
        col = int(item.column())
        text = str(item.text() or "").strip()
        try:
            if col == 2:
                mapping["cc"] = max(0, min(127, int(text)))
            elif col == 3:
                channel_one_based = max(1, min(16, int(text)))
                mapping["channel"] = int(channel_one_based - 1)
            elif col == 4:
                mapping["min"] = float(text)
            elif col == 5:
                mapping["max"] = float(text)
            else:
                return
        except ValueError:
            self._refresh_midi_mapping_table()
            return
        self._persist_midi_mapping_state()

    def _on_midi_channel_filter_changed(self, _index: int) -> None:
        value = self.midi_channel_combo.currentData() if hasattr(self, "midi_channel_combo") else -1
        if self._midi_worker is not None and isinstance(value, int):
            self._midi_worker.set_channel_filter(int(value))
        self._persist_midi_mapping_state()

    def _on_midi_device_selection_changed(self, _row: int) -> None:
        if not hasattr(self, "midi_device_list"):
            return
        item = self.midi_device_list.currentItem()
        if item is None:
            self.midi_device_status_label.setText("No MIDI device selected")
            self.midi_device_status_dot.setStyleSheet("color:#f0b55a; font-size:18px;")
            if self._midi_worker is not None:
                self._midi_worker.set_selected_device("")
            return
        name = str(item.data(Qt.ItemDataRole.UserRole) or item.text())
        self.midi_device_status_label.setText(f"Selected: {name}")
        self.midi_device_status_dot.setStyleSheet("color:#6ce47a; font-size:18px;")
        if self._midi_worker is not None:
            self._midi_worker.set_selected_device(name)
        self._append_midi_console(f"Selected MIDI input: {name}")

    def _on_midi_worker_devices(self, names: list) -> None:
        self._midi_input_devices = [str(name) for name in names]
        if not hasattr(self, "midi_device_list"):
            return
        previous = ""
        current_item = self.midi_device_list.currentItem()
        if current_item is not None:
            previous = str(current_item.data(Qt.ItemDataRole.UserRole) or current_item.text())
        self.midi_device_list.blockSignals(True)
        self.midi_device_list.clear()
        for name in self._midi_input_devices:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.midi_device_list.addItem(item)
        self.midi_device_list.blockSignals(False)

        if not self._midi_input_devices:
            self.midi_device_status_label.setText("No MIDI inputs detected")
            self.midi_device_status_dot.setStyleSheet("color:#f16f6f; font-size:18px;")
            return

        target_name = previous if previous in self._midi_input_devices else self._midi_input_devices[0]
        for idx in range(self.midi_device_list.count()):
            item = self.midi_device_list.item(idx)
            if item is not None and str(item.data(Qt.ItemDataRole.UserRole)) == target_name:
                self.midi_device_list.setCurrentRow(idx)
                break
        self._on_midi_device_selection_changed(self.midi_device_list.currentRow())

    def _on_midi_worker_status(self, message: str) -> None:
        text = str(message).strip()
        if not text:
            return
        self._append_midi_console(text)

    def _refresh_midi_devices(self) -> None:
        if self._midi_worker is not None:
            self._midi_worker.refresh_devices()
            return

        names: list[str] = []
        try:
            import mido  # type: ignore

            names = [str(name) for name in mido.get_input_names()]
        except Exception:
            names = []
        self._on_midi_worker_devices(names)

    def _start_midi_input_worker(self) -> None:
        if self._midi_worker_thread is not None and self._midi_worker_thread.isRunning():
            return
        worker_thread = QThread(self)
        worker = MidiInputWorker()
        worker.moveToThread(worker_thread)
        worker_thread.started.connect(worker.run)
        worker.cc_message.connect(self._on_midi_input_event)
        worker.status.connect(self._on_midi_worker_status)
        worker.devices.connect(self._on_midi_worker_devices)
        worker_thread.start()
        self._midi_worker_thread = worker_thread
        self._midi_worker = worker
        selected_channel = self.midi_channel_combo.currentData() if hasattr(self, "midi_channel_combo") else -1
        if isinstance(selected_channel, int):
            worker.set_channel_filter(int(selected_channel))
        self._refresh_midi_devices()

    def _on_midi_input_event(self, event: dict) -> None:
        if not isinstance(event, dict):
            return
        if str(event.get("kind", "")) != "cc":
            return
        channel = int(event.get("channel", -1))
        cc = int(event.get("cc", -1))
        value_raw = int(event.get("value_raw", 0))
        value_norm = float(event.get("value_norm", 0.0))

        self._append_midi_console(f"CC {cc} ch {channel + 1} value {value_raw}")

        if self._midi_learn_active and self._midi_learn_pending_row is not None:
            row = int(self._midi_learn_pending_row)
            if 0 <= row < len(self._midi_mapping_rows):
                mapping = self._midi_mapping_rows[row]
                mapping["cc"] = int(cc)
                mapping["channel"] = int(channel)
                self.midi_learn_confirmation_label.setText(
                    f"Assigned {mapping['category']} / {mapping['parameter']} to CC {cc} on channel {channel + 1}."
                )
                self._append_midi_console(
                    f"Learn captured: {mapping['parameter']} -> CC {cc} ch {channel + 1}"
                )
                self._midi_learn_pending_row = None
                self._refresh_midi_mapping_table()
                self._persist_midi_mapping_state()

        self._apply_midi_control_change(channel=channel, cc=cc, normalized=value_norm)

    def _apply_midi_control_change(self, *, channel: int, cc: int, normalized: float) -> None:
        updated = False
        for mapping in self._midi_mapping_rows:
            if int(mapping.get("cc", -1)) != int(cc):
                continue
            if int(mapping.get("channel", -1)) != int(channel):
                continue
            min_value = float(mapping.get("min", 0.0))
            max_value = float(mapping.get("max", 1.0))
            curve = str(mapping.get("curve", "Linear")).strip().lower()
            mapped_norm = max(0.0, min(1.0, float(normalized)))
            if curve == "log":
                mapped_norm = mapped_norm * mapped_norm
            elif curve == "exp":
                mapped_norm = mapped_norm ** 0.5
            mapped_value = min_value + ((max_value - min_value) * mapped_norm)
            mapping["current"] = float(mapped_value)
            updated = True

            parameter = str(mapping.get("parameter", ""))
            if parameter == "Master Volume":
                if hasattr(self, "main_mixer_view"):
                    self.main_mixer_view.on_master_volume_change(mapped_value)
            elif parameter == "Selected Track Volume":
                if self.selected_track_index is not None and 0 <= int(self.selected_track_index) < len(self.current_project.tracks):
                    self._on_track_volume_changed(int(self.selected_track_index), float(mapped_value * 12.0) - 6.0)
            elif parameter == "Selected Track Pan":
                if self.selected_track_index is not None and 0 <= int(self.selected_track_index) < len(self.current_project.tracks):
                    self._on_track_pan_changed(int(self.selected_track_index), float(mapped_value))

        if updated:
            self._refresh_midi_mapping_table()
            self._persist_midi_mapping_state()

    def _build_help_tab(self) -> QWidget:
        return build_help_tab(self)

    def _default_settings_shortcuts(self) -> dict[str, str]:
        return {
            "Play/Stop": "Space",
            "Record": "R",
            "Jump To Start": "Home",
            "Jump To End": "End",
            "Undo": "Ctrl+Z",
            "Redo": "Ctrl+Y",
            "Save Project": "Ctrl+S",
            "Delete Clip": "Delete",
            "Split At Playhead": "S",
            "New Track": "Ctrl+T",
            "Mute Track": "M",
            "Solo Track": "Alt+S",
            "Zoom (Timeline)": "Ctrl+Scroll",
            "Open Stem Separation": "Ctrl+D",
            "Open ACE-Step": "Ctrl+E",
            "Open Mastering": "Ctrl+M",
            "MIDI Learn Mode": "Ctrl+L",
            "New Project": "Ctrl+N",
            "Open Project": "Ctrl+O",
            "Export": "Ctrl+Shift+E",
        }

    def _initialize_settings_state(self) -> None:
        if self._settings_state is not None:
            return
        stored = self.current_project.metadata.get("settings_page")
        stored_dict = stored if isinstance(stored, dict) else {}
        project_defaults_raw = stored_dict.get("project_defaults")
        project_defaults = project_defaults_raw if isinstance(project_defaults_raw, dict) else {}
        appearance_raw = stored_dict.get("appearance")
        appearance = appearance_raw if isinstance(appearance_raw, dict) else {}
        model_defaults_raw = stored_dict.get("model_defaults")
        model_defaults = model_defaults_raw if isinstance(model_defaults_raw, dict) else {}
        shortcuts_raw = stored_dict.get("shortcuts")
        shortcuts = shortcuts_raw if isinstance(shortcuts_raw, dict) else {}

        merged_shortcuts = self._default_settings_shortcuts()
        merged_shortcuts.update({str(k): str(v) for k, v in shortcuts.items()})

        self._settings_state = {
            "audio": {
                "backend": str(stored_dict.get("audio_backend", "WASAPI Shared")),
                "bit_depth": int(stored_dict.get("audio_bit_depth", 24)),
            },
            "model_defaults": {
                "demucs": str(model_defaults.get("demucs", DEFAULT_DEMUCS_MODEL)),
                "ace": str(model_defaults.get("ace", "")),
            },
            "appearance": {
                "theme": str(appearance.get("theme", "Dark Studio")),
                "accent_color": str(appearance.get("accent_color", "#00F0FF")),
                "font_size": str(appearance.get("font_size", "Medium")),
                "waveform_color_mode": str(appearance.get("waveform_color_mode", "Per-track")),
                "animation_speed": str(appearance.get("animation_speed", "Full")),
            },
            "shortcuts": merged_shortcuts,
            "project_defaults": {
                "folder": str(project_defaults.get("folder", self._default_new_project_folder())),
                "sample_rate": int(project_defaults.get("sample_rate", int(device_manager.selected_sample_rate))),
                "bpm": int(project_defaults.get("bpm", int(self.recording_controller.status.current_tempo_bpm))),
                "autosave_interval_minutes": int(project_defaults.get("autosave_interval_minutes", 5)),
                "autosave_location": str(project_defaults.get("autosave_location", self._default_new_project_folder())),
            },
        }

    def _persist_settings_state(self) -> None:
        if self._settings_state is None:
            return
        self.current_project.metadata["settings_page"] = copy.deepcopy(self._settings_state)
        self._refresh_status_bar_telemetry()

    def _refresh_settings_page(self) -> None:
        self._initialize_settings_state()
        if self._settings_state is None:
            return

        audio_state = self._settings_state["audio"]
        if hasattr(self, "settings_audio_backend_combo"):
            idx = self.settings_audio_backend_combo.findText(str(audio_state.get("backend", "WASAPI Shared")))
            if idx >= 0:
                self.settings_audio_backend_combo.setCurrentIndex(idx)
        if hasattr(self, "settings_audio_bit_depth_combo"):
            idx = self.settings_audio_bit_depth_combo.findData(int(audio_state.get("bit_depth", 24)))
            if idx >= 0:
                self.settings_audio_bit_depth_combo.setCurrentIndex(idx)

        appearance = self._settings_state["appearance"]
        if hasattr(self, "settings_theme_combo"):
            idx = self.settings_theme_combo.findText(str(appearance.get("theme", "Dark Studio")))
            if idx >= 0:
                self.settings_theme_combo.setCurrentIndex(idx)
        if hasattr(self, "settings_accent_input"):
            self.settings_accent_input.setText(str(appearance.get("accent_color", "#00F0FF")))
        if hasattr(self, "settings_font_size_combo"):
            idx = self.settings_font_size_combo.findText(str(appearance.get("font_size", "Medium")))
            if idx >= 0:
                self.settings_font_size_combo.setCurrentIndex(idx)
        if hasattr(self, "settings_waveform_color_mode_combo"):
            idx = self.settings_waveform_color_mode_combo.findText(str(appearance.get("waveform_color_mode", "Per-track")))
            if idx >= 0:
                self.settings_waveform_color_mode_combo.setCurrentIndex(idx)
        if hasattr(self, "settings_animation_speed_combo"):
            idx = self.settings_animation_speed_combo.findText(str(appearance.get("animation_speed", "Full")))
            if idx >= 0:
                self.settings_animation_speed_combo.setCurrentIndex(idx)

        defaults = self._settings_state["project_defaults"]
        if hasattr(self, "settings_default_project_folder_input"):
            self.settings_default_project_folder_input.setText(str(defaults.get("folder", self._default_new_project_folder())))
        if hasattr(self, "settings_default_sample_rate_combo"):
            idx = self.settings_default_sample_rate_combo.findData(int(defaults.get("sample_rate", 44100)))
            if idx >= 0:
                self.settings_default_sample_rate_combo.setCurrentIndex(idx)
        if hasattr(self, "settings_default_bpm_spin"):
            self.settings_default_bpm_spin.setValue(int(defaults.get("bpm", 120)))
        if hasattr(self, "settings_default_autosave_interval_spin"):
            self.settings_default_autosave_interval_spin.setValue(int(defaults.get("autosave_interval_minutes", 5)))
        if hasattr(self, "settings_default_autosave_location_input"):
            self.settings_default_autosave_location_input.setText(str(defaults.get("autosave_location", self._default_new_project_folder())))

        self._settings_refresh_audio_devices()
        self._settings_refresh_model_tables()
        self._settings_refresh_shortcuts_table()

    def _settings_refresh_audio_devices(self) -> None:
        if not hasattr(self, "settings_audio_input_combo") or not hasattr(self, "settings_audio_output_combo"):
            return

        device_manager.refresh_devices()
        input_devices = device_manager.get_input_devices()
        output_devices = device_manager.get_output_devices()

        self.settings_audio_input_combo.blockSignals(True)
        self.settings_audio_output_combo.blockSignals(True)
        self.settings_audio_input_combo.clear()
        self.settings_audio_output_combo.clear()

        for device in input_devices:
            label = f"{device.device_id}: {device.name}"
            if device.is_default_input:
                label += " [Default]"
            self.settings_audio_input_combo.addItem(label, device.device_id)

        for device in output_devices:
            label = f"{device.device_id}: {device.name}"
            if device.is_default_output:
                label += " [Default]"
            self.settings_audio_output_combo.addItem(label, device.device_id)

        input_idx = self.settings_audio_input_combo.findData(device_manager.selected_input_device)
        output_idx = self.settings_audio_output_combo.findData(device_manager.selected_output_device)
        if input_idx >= 0:
            self.settings_audio_input_combo.setCurrentIndex(input_idx)
        if output_idx >= 0:
            self.settings_audio_output_combo.setCurrentIndex(output_idx)

        if hasattr(self, "settings_audio_sample_rate_combo"):
            sr_idx = self.settings_audio_sample_rate_combo.findData(int(device_manager.selected_sample_rate))
            if sr_idx >= 0:
                self.settings_audio_sample_rate_combo.setCurrentIndex(sr_idx)
        if hasattr(self, "settings_audio_buffer_combo"):
            buffer_idx = self.settings_audio_buffer_combo.findData(int(device_manager.selected_buffer_size))
            if buffer_idx >= 0:
                self.settings_audio_buffer_combo.setCurrentIndex(buffer_idx)

        self.settings_audio_input_combo.blockSignals(False)
        self.settings_audio_output_combo.blockSignals(False)

        self._settings_refresh_audio_engine_status()

    def _settings_refresh_audio_engine_status(self) -> None:
        if not hasattr(self, "settings_audio_latency_label") or not hasattr(self, "settings_audio_driver_status_label"):
            return

        selected_input = self.settings_audio_input_combo.currentData() if hasattr(self, "settings_audio_input_combo") else None
        selected_output = self.settings_audio_output_combo.currentData() if hasattr(self, "settings_audio_output_combo") else None
        sample_rate = self.settings_audio_sample_rate_combo.currentData() if hasattr(self, "settings_audio_sample_rate_combo") else None
        buffer_size = self.settings_audio_buffer_combo.currentData() if hasattr(self, "settings_audio_buffer_combo") else None

        if isinstance(selected_input, int):
            device_manager.select_input_device(int(selected_input))
        if isinstance(selected_output, int):
            device_manager.select_output_device(int(selected_output))
        if isinstance(sample_rate, int) and sample_rate > 0:
            device_manager.set_sample_rate(int(sample_rate))
        if isinstance(buffer_size, int) and buffer_size > 0:
            device_manager.set_buffer_size(int(buffer_size))

        total_latency = float(device_manager.get_total_latency())
        self.settings_audio_latency_label.setText(f"Latency: {total_latency:.1f} ms round trip")
        ok, message = device_manager.test_device_configuration()
        if ok:
            self.settings_audio_driver_status_label.setText(f"Driver status: Ready ({message})")
            self.settings_audio_driver_status_label.setStyleSheet("color:#6ce47a;")
        else:
            self.settings_audio_driver_status_label.setText(f"Driver status: Warning ({message})")
            self.settings_audio_driver_status_label.setStyleSheet("color:#f0b55a;")

    def _settings_apply_audio_engine(self) -> None:
        if self._settings_state is None:
            return
        input_id = self.settings_audio_input_combo.currentData() if hasattr(self, "settings_audio_input_combo") else None
        output_id = self.settings_audio_output_combo.currentData() if hasattr(self, "settings_audio_output_combo") else None
        sample_rate = self.settings_audio_sample_rate_combo.currentData() if hasattr(self, "settings_audio_sample_rate_combo") else None
        buffer_size = self.settings_audio_buffer_combo.currentData() if hasattr(self, "settings_audio_buffer_combo") else None
        backend = self.settings_audio_backend_combo.currentText() if hasattr(self, "settings_audio_backend_combo") else "WASAPI Shared"
        bit_depth = self.settings_audio_bit_depth_combo.currentData() if hasattr(self, "settings_audio_bit_depth_combo") else 24

        if not isinstance(input_id, int) or not isinstance(output_id, int):
            QMessageBox.warning(self, "Settings", "Select both input and output devices.")
            return

        device_manager.select_input_device(int(input_id))
        device_manager.select_output_device(int(output_id))
        if isinstance(sample_rate, int) and sample_rate > 0:
            device_manager.set_sample_rate(int(sample_rate))
            if hasattr(self, "sample_rate_combo"):
                sr_idx = self.sample_rate_combo.findData(int(sample_rate))
                if sr_idx >= 0:
                    self.sample_rate_combo.setCurrentIndex(sr_idx)
        if isinstance(buffer_size, int) and buffer_size > 0:
            device_manager.set_buffer_size(int(buffer_size))

        self._settings_state["audio"] = {
            "backend": str(backend),
            "bit_depth": int(bit_depth) if isinstance(bit_depth, int) else 24,
        }
        self._persist_settings_state()
        self._settings_refresh_audio_engine_status()
        self._refresh_status_bar_telemetry()
        self.update_status("Audio engine settings applied")

    def _settings_play_test_tone(self) -> None:
        try:
            import winsound

            winsound.Beep(1000, 300)
            self.update_status("Played 1 kHz test tone")
            return
        except Exception:
            pass

        QApplication.beep()
        self.update_status("Played system beep as test tone fallback")

    def _settings_model_target_dir(self, kind: str) -> Path:
        if str(kind).strip().lower() == "demucs":
            target = MODELS_DIR / "demucs" / "custom"
        else:
            target = ACE_MODELS_DIR / "custom"
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _settings_human_size(self, size_bytes: int) -> str:
        size = float(max(0, int(size_bytes)))
        units = ["B", "KB", "MB", "GB"]
        idx = 0
        while size >= 1024.0 and idx < len(units) - 1:
            size /= 1024.0
            idx += 1
        return f"{size:.1f} {units[idx]}"

    def _settings_model_inventory(self, kind: str) -> list[dict]:
        records: list[dict] = []
        normalized = str(kind).strip().lower()
        if normalized == "demucs":
            for model_name, label in DEMUCS_MODEL_OPTIONS:
                stems_text = "4 stems"
                if "6" in label:
                    stems_text = "6 stems"
                records.append(
                    {
                        "id": model_name,
                        "name": model_name,
                        "type": stems_text,
                        "size": "bundled",
                        "date": "runtime",
                        "source": "Built-in",
                        "path": None,
                        "details": f"{label}. Recommended for standard stem separation workloads.",
                    }
                )
            demucs_custom = self._settings_model_target_dir("demucs")
            for entry in sorted(demucs_custom.iterdir(), key=lambda item: item.name.lower()):
                if not (entry.is_dir() or entry.suffix.lower() in {".pt", ".th"}):
                    continue
                size_bytes = 0
                if entry.is_file():
                    size_bytes = int(entry.stat().st_size)
                else:
                    size_bytes = sum(int(p.stat().st_size) for p in entry.rglob("*") if p.is_file())
                stamp = time.strftime("%Y-%m-%d", time.localtime(entry.stat().st_mtime))
                records.append(
                    {
                        "id": str(entry.resolve()),
                        "name": entry.name,
                        "type": "Custom",
                        "size": self._settings_human_size(size_bytes),
                        "date": stamp,
                        "source": "Local",
                        "path": entry,
                        "details": "Custom Demucs model asset. Use Set Default to choose it for new splits.",
                    }
                )
            return records

        ace_custom = self._settings_model_target_dir("ace")
        for entry in sorted(ace_custom.iterdir(), key=lambda item: item.name.lower()):
            if not (entry.is_file() and entry.suffix.lower() in {".safetensors", ".ckpt", ".pt"}):
                continue
            size_bytes = int(entry.stat().st_size)
            stamp = time.strftime("%Y-%m-%d", time.localtime(entry.stat().st_mtime))
            records.append(
                {
                    "id": str(entry.resolve()),
                    "name": entry.name,
                    "type": "Checkpoint",
                    "size": self._settings_human_size(size_bytes),
                    "date": stamp,
                    "source": "Local",
                    "path": entry,
                    "details": "ACE-Step model file. Select as default to preselect in AI Generation tab.",
                }
            )
        return records

    def _settings_refresh_model_tables(self) -> None:
        if self._settings_state is None:
            return
        tables = getattr(self, "_settings_model_tables", None)
        if not isinstance(tables, dict):
            return

        for kind, table in tables.items():
            entries = self._settings_model_inventory(str(kind))
            table.setRowCount(0)
            for row_idx, entry in enumerate(entries):
                table.insertRow(row_idx)
                name_item = QTableWidgetItem(str(entry.get("name", "")))
                name_item.setData(Qt.ItemDataRole.UserRole, entry)
                table.setItem(row_idx, 0, name_item)
                table.setItem(row_idx, 1, QTableWidgetItem(str(entry.get("type", ""))))
                table.setItem(row_idx, 2, QTableWidgetItem(str(entry.get("size", ""))))
                table.setItem(row_idx, 3, QTableWidgetItem(str(entry.get("date", ""))))

                set_default_btn = QPushButton("Set Default")
                set_default_btn.clicked.connect(lambda _checked=False, k=str(kind), model_id=str(entry.get("id", "")): self._settings_set_default_model(k, model_id))
                table.setCellWidget(row_idx, 4, set_default_btn)

                remove_btn = QPushButton("Remove")
                remove_btn.clicked.connect(lambda _checked=False, k=str(kind), model_id=str(entry.get("id", "")): self._settings_remove_model(k, model_id))
                table.setCellWidget(row_idx, 5, remove_btn)

                table.setItem(row_idx, 6, QTableWidgetItem(str(entry.get("source", ""))))

            if table.rowCount() > 0:
                table.selectRow(0)
                self._settings_on_model_selection_changed(str(kind))

    def _settings_on_model_selection_changed(self, kind: str) -> None:
        tables = getattr(self, "_settings_model_tables", {})
        details_map = getattr(self, "_settings_model_details", {})
        table = tables.get(str(kind))
        details_view = details_map.get(str(kind))
        if table is None or details_view is None:
            return
        row = table.currentRow()
        if row < 0:
            details_view.clear()
            return
        item = table.item(row, 0)
        if item is None:
            details_view.clear()
            return
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            details_view.clear()
            return
        details_view.setPlainText(str(payload.get("details", "No details available.")))

    def _settings_set_default_model(self, kind: str, model_id: str) -> None:
        self._initialize_settings_state()
        if self._settings_state is None:
            return
        normalized = str(kind).strip().lower()
        self._settings_state["model_defaults"][normalized] = str(model_id)
        self._persist_settings_state()

        if normalized == "demucs" and hasattr(self, "stem_model_combo"):
            idx = self.stem_model_combo.findData(str(model_id))
            if idx >= 0:
                self.stem_model_combo.setCurrentIndex(idx)
        if normalized == "ace" and hasattr(self, "ace_model_combo"):
            idx = self.ace_model_combo.findData(str(model_id))
            if idx >= 0:
                self.ace_model_combo.setCurrentIndex(idx)

        self.update_status(f"Default {normalized} model set")

    def _settings_remove_model(self, kind: str, model_id: str) -> None:
        normalized = str(kind).strip().lower()
        target = None
        for entry in self._settings_model_inventory(normalized):
            if str(entry.get("id", "")) == str(model_id):
                target = entry
                break
        if target is None:
            return
        path = target.get("path")
        if not isinstance(path, Path):
            QMessageBox.information(self, "Settings", "Built-in models cannot be removed.")
            return

        confirm = QMessageBox.question(
            self,
            "Remove model",
            f"Remove model asset '{path.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        except Exception as exc:
            QMessageBox.warning(self, "Settings", f"Could not remove model:\n{exc}")
            return

        self._settings_refresh_model_tables()
        self.update_status(f"Removed model asset: {path.name}")

    def _settings_unique_target(self, target_dir: Path, source_name: str) -> Path:
        candidate = target_dir / source_name
        if not candidate.exists():
            return candidate
        stem = Path(source_name).stem
        suffix = Path(source_name).suffix
        index = 1
        while True:
            candidate = target_dir / f"{stem}_{index}{suffix}"
            if not candidate.exists():
                return candidate
            index += 1

    def _settings_add_model_from_folder(self, kind: str) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select model folder", str(self._settings_model_target_dir(kind)))
        if not folder:
            return
        root = Path(folder)
        paths: list[Path] = []
        if str(kind).strip().lower() == "demucs":
            for entry in root.iterdir():
                if entry.is_dir() or (entry.is_file() and entry.suffix.lower() in {".pt", ".th"}):
                    paths.append(entry)
        else:
            for entry in root.rglob("*"):
                if entry.is_file() and entry.suffix.lower() in {".safetensors", ".ckpt", ".pt"}:
                    paths.append(entry)
        if not paths:
            QMessageBox.information(self, "Settings", "No supported model assets found in the selected folder.")
            return
        self._settings_install_model_from_paths(kind, paths)

    def _settings_install_model_from_paths(self, kind: str, paths: list[Path]) -> None:
        target_dir = self._settings_model_target_dir(kind)
        installed = 0
        normalized = str(kind).strip().lower()
        for path in paths:
            src = Path(path)
            if not src.exists():
                continue
            try:
                if src.is_dir() and normalized == "demucs":
                    destination = self._settings_unique_target(target_dir, src.name)
                    shutil.copytree(src, destination)
                    installed += 1
                    continue

                if not src.is_file():
                    continue
                if normalized == "demucs" and src.suffix.lower() not in {".pt", ".th"}:
                    continue
                if normalized == "ace" and src.suffix.lower() not in {".safetensors", ".ckpt", ".pt"}:
                    continue

                destination = self._settings_unique_target(target_dir, src.name)
                shutil.copy2(str(src), str(destination))
                installed += 1
            except Exception:
                continue

        self._settings_refresh_model_tables()
        self.update_status(f"Installed {installed} {normalized} model asset(s)")

    def _settings_download_model_from_url(self, kind: str) -> None:
        url_inputs = getattr(self, "_settings_model_url_inputs", {})
        progress_bars = getattr(self, "_settings_model_progress_bars", {})
        url_input = url_inputs.get(str(kind))
        progress_bar = progress_bars.get(str(kind))
        if url_input is None or progress_bar is None:
            return

        url = str(url_input.text() or "").strip()
        if not url:
            QMessageBox.warning(self, "Settings", "Enter a model URL first.")
            return

        parsed = urllib.parse.urlparse(url)
        filename = Path(parsed.path).name
        if not filename:
            QMessageBox.warning(self, "Settings", "Could not infer a filename from the URL.")
            return

        normalized = str(kind).strip().lower()
        allowed = {".pt", ".th"} if normalized == "demucs" else {".safetensors", ".ckpt", ".pt"}
        if Path(filename).suffix.lower() not in allowed:
            QMessageBox.warning(self, "Settings", f"Unsupported model extension for {normalized}: {Path(filename).suffix}")
            return

        target_dir = self._settings_model_target_dir(normalized)
        destination = self._settings_unique_target(target_dir, filename)
        progress_bar.setValue(0)

        def _hook(block_count: int, block_size: int, total_size: int) -> None:
            if total_size <= 0:
                progress_bar.setValue(0)
            else:
                percent = max(0, min(100, int((block_count * block_size * 100) / total_size)))
                progress_bar.setValue(percent)
            QApplication.processEvents()

        try:
            urllib.request.urlretrieve(url, str(destination), _hook)
        except Exception as exc:
            QMessageBox.warning(self, "Settings", f"Download failed:\n{exc}")
            progress_bar.setValue(0)
            return

        progress_bar.setValue(100)
        self._settings_refresh_model_tables()
        self.update_status(f"Downloaded model asset: {destination.name}")

    def _settings_refresh_shortcuts_table(self, _text: Optional[str] = None) -> None:
        self._initialize_settings_state()
        if self._settings_state is None or not hasattr(self, "settings_shortcuts_table"):
            return

        search_term = ""
        if hasattr(self, "settings_shortcut_search_input"):
            search_term = str(self.settings_shortcut_search_input.text() or "").strip().lower()

        entries = list(self._settings_state["shortcuts"].items())
        if search_term:
            entries = [(action, key) for action, key in entries if search_term in action.lower()]

        table = self.settings_shortcuts_table
        self._settings_shortcut_table_syncing = True
        table.setRowCount(0)
        for row_idx, (action, keybind) in enumerate(entries):
            table.insertRow(row_idx)
            action_item = QTableWidgetItem(str(action))
            action_item.setFlags(action_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            action_item.setData(Qt.ItemDataRole.UserRole, str(action))
            table.setItem(row_idx, 0, action_item)
            table.setItem(row_idx, 1, QTableWidgetItem(str(keybind)))
        self._settings_shortcut_table_syncing = False

    def _settings_on_shortcut_item_changed(self, item: QTableWidgetItem) -> None:
        if self._settings_shortcut_table_syncing or self._settings_state is None:
            return
        if item.column() != 1:
            return
        action_item = self.settings_shortcuts_table.item(item.row(), 0)
        if action_item is None:
            return
        action = str(action_item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not action:
            return
        keybind = str(item.text() or "").strip()
        self._settings_state["shortcuts"][action] = keybind
        self._persist_settings_state()
        if hasattr(self, "_register_global_shortcuts"):
            self._register_global_shortcuts()
        self.update_status(f"Shortcut updated: {action} -> {keybind}")

    def _settings_reset_shortcuts_to_defaults(self) -> None:
        self._initialize_settings_state()
        if self._settings_state is None:
            return
        self._settings_state["shortcuts"] = self._default_settings_shortcuts()
        self._persist_settings_state()
        self._settings_refresh_shortcuts_table()
        if hasattr(self, "_register_global_shortcuts"):
            self._register_global_shortcuts()
        self.update_status("Shortcut mappings reset to defaults")

    def _settings_apply_appearance(self) -> None:
        self._initialize_settings_state()
        if self._settings_state is None:
            return

        accent = str(self.settings_accent_input.text() if hasattr(self, "settings_accent_input") else "#00F0FF").strip()
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", accent):
            QMessageBox.warning(self, "Settings", "Accent color must be a hex value like #00F0FF.")
            return

        self._settings_state["appearance"] = {
            "theme": str(self.settings_theme_combo.currentText() if hasattr(self, "settings_theme_combo") else "Dark Studio"),
            "accent_color": accent,
            "font_size": str(self.settings_font_size_combo.currentText() if hasattr(self, "settings_font_size_combo") else "Medium"),
            "waveform_color_mode": str(self.settings_waveform_color_mode_combo.currentText() if hasattr(self, "settings_waveform_color_mode_combo") else "Per-track"),
            "animation_speed": str(self.settings_animation_speed_combo.currentText() if hasattr(self, "settings_animation_speed_combo") else "Full"),
        }
        self._persist_settings_state()
        self.update_status("Appearance settings saved")

    def _settings_browse_default_project_folder(self) -> None:
        if not hasattr(self, "settings_default_project_folder_input"):
            return
        folder = QFileDialog.getExistingDirectory(self, "Select default project folder", self.settings_default_project_folder_input.text().strip() or str(self._default_new_project_folder()))
        if folder:
            self.settings_default_project_folder_input.setText(folder)

    def _settings_save_project_defaults(self) -> None:
        self._initialize_settings_state()
        if self._settings_state is None:
            return

        folder = Path(str(self.settings_default_project_folder_input.text() if hasattr(self, "settings_default_project_folder_input") else "").strip() or str(self._default_new_project_folder()))
        autosave_location = Path(str(self.settings_default_autosave_location_input.text() if hasattr(self, "settings_default_autosave_location_input") else "").strip() or str(folder))
        try:
            folder.mkdir(parents=True, exist_ok=True)
            autosave_location.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "Settings", f"Could not create default folders:\n{exc}")
            return

        sample_rate = self.settings_default_sample_rate_combo.currentData() if hasattr(self, "settings_default_sample_rate_combo") else 44100
        bpm = int(self.settings_default_bpm_spin.value()) if hasattr(self, "settings_default_bpm_spin") else 120
        autosave_interval = int(self.settings_default_autosave_interval_spin.value()) if hasattr(self, "settings_default_autosave_interval_spin") else 5

        self._settings_state["project_defaults"] = {
            "folder": str(folder),
            "sample_rate": int(sample_rate) if isinstance(sample_rate, int) else 44100,
            "bpm": bpm,
            "autosave_interval_minutes": autosave_interval,
            "autosave_location": str(autosave_location),
        }
        self._persist_settings_state()
        self.update_status("Project defaults saved")



    def _rebuild_mixer_rows(self):
        # Remove all items except the trailing stretch
        while self.mixer_layout.count() > 1:
            item = self.mixer_layout.takeAt(0)
            if item is None:  # safety guard: Qt should never return None here, but guard defensively
                continue
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.mixer_rows = []
        has_tracks = bool(self.current_project.tracks)
        if not has_tracks:
            self.mixer_empty_label.setParent(self.mixer_inner)
            self.mixer_layout.insertWidget(0, self.mixer_empty_label)
        for idx, track in enumerate(self.current_project.tracks):
            row = TrackMixerRow(
                idx,
                track.name,
                on_volume_change=self._on_track_volume_changed,
                on_pan_change=self._on_track_pan_changed,
                on_mute_toggle=self._set_track_muted,
                on_solo_toggle=self._set_track_soloed,
                on_arm_toggle=self._set_track_armed,
                on_name_change=self._rename_track_from_mixer,
                on_color_change=self._set_track_color,
                on_input_change=self._set_track_input_source,
                on_send_change=self._on_track_send_changed,
                on_automation_param_change=self._on_track_automation_parameter_changed,
                on_open_playback_settings=self._open_track_playback_settings,
            )
            row.set_volume_db(track.volume_db)
            row.set_pan(getattr(track, "pan", 0.0))
            row.set_mute(track.muted)
            row.set_solo(track.soloed)
            row.set_armed(idx in self.recording_controller.status.active_track_ids)
            row.set_track_name(track.name)
            row.set_track_color(getattr(track, "color_hex", "#00F0FF"))
            row.set_input_source(getattr(track, "input_source", "Auto"))
            row.set_send_levels(float(getattr(track, "send_a", 0.0)), float(getattr(track, "send_b", 0.0)))
            row.set_automation_parameter(self._track_automation_parameter(idx))
            summary, tooltip = self._track_playback_summary(track)
            row.set_playback_summary(summary, tooltip)
            self.mixer_layout.insertWidget(self.mixer_layout.count() - 1, row)
            self.mixer_rows.append(row)

        self.mixer_layout.insertWidget(self.mixer_layout.count() - 1, self._build_add_track_strip_widget())

    def _on_track_volume_changed(self, track_index: int, db: float) -> None:
        if 0 <= track_index < len(self.current_project.tracks):
            track = self.current_project.tracks[track_index]
            current_value = float(getattr(track, "volume_db", 0.0))
            next_value = float(db)
            if abs(current_value - next_value) <= 1e-6:
                return
            pre_change_snapshot = self._snapshot_project_edit_state()
            track.volume_db = next_value
            self._push_project_snapshot(f"Track {track_index + 1} volume", pre_change_snapshot)
            self.sync_project_tracks_to_recording_engine()
            self._refresh_active_project_playback_mix(f"track {track_index + 1} volume")
            self.update_status(f"Track {track_index + 1} volume: {next_value:+.0f} dB")

    def _on_track_pan_changed(self, track_index: int, pan: float) -> None:
        if 0 <= track_index < len(self.current_project.tracks):
            track = self.current_project.tracks[track_index]
            current_value = float(getattr(track, "pan", 0.0))
            next_value = max(-1.0, min(1.0, float(pan)))
            if abs(current_value - next_value) <= 1e-6:
                return
            pre_change_snapshot = self._snapshot_project_edit_state()
            track.pan = next_value
            self._push_project_snapshot(f"Track {track_index + 1} pan", pre_change_snapshot)
            self.sync_project_tracks_to_recording_engine()
            self._refresh_active_project_playback_mix(f"track {track_index + 1} pan")
            self.update_status(f"Track {track_index + 1} pan: {track.pan:+.2f}")

    def _on_track_send_changed(self, track_index: int, bus: str, level: float) -> None:
        if not (0 <= track_index < len(self.current_project.tracks)):
            return
        track = self.current_project.tracks[track_index]
        normalized = max(0.0, min(1.0, float(level)))
        pre_change_snapshot = self._snapshot_project_edit_state()
        if str(bus).lower() == "a":
            current_value = float(getattr(track, "send_a", 0.0))
            if abs(current_value - normalized) <= 1e-6:
                return
            track.send_a = normalized
            bus_name = "Bus 1"
        else:
            current_value = float(getattr(track, "send_b", 0.0))
            if abs(current_value - normalized) <= 1e-6:
                return
            track.send_b = normalized
            bus_name = "Bus 2"
        self._push_project_snapshot(f"Track {track_index + 1} {bus_name} send", pre_change_snapshot)
        self._refresh_active_project_playback_mix(f"track {track_index + 1} {bus_name} send")
        self.update_status(f"Track {track_index + 1} {bus_name} send: {int(round(normalized * 100.0))}%")

    def _set_track_muted(self, track_index: int, muted: bool) -> None:
        if 0 <= track_index < len(self.current_project.tracks):
            track = self.current_project.tracks[track_index]
            next_value = bool(muted)
            if bool(getattr(track, "muted", False)) == next_value:
                return
            pre_change_snapshot = self._snapshot_project_edit_state()
            track.muted = next_value
            self._push_project_snapshot(f"Track {track_index + 1} mute", pre_change_snapshot)
            self.sync_project_tracks_to_recording_engine()
            self._refresh_active_project_playback_mix(f"track {track_index + 1} mute")
            self.refresh_track_list()

    def _set_track_soloed(self, track_index: int, soloed: bool) -> None:
        if 0 <= track_index < len(self.current_project.tracks):
            track = self.current_project.tracks[track_index]
            next_value = bool(soloed)
            if bool(getattr(track, "soloed", False)) == next_value:
                return
            pre_change_snapshot = self._snapshot_project_edit_state()
            track.soloed = next_value
            self._push_project_snapshot(f"Track {track_index + 1} solo", pre_change_snapshot)
            self.sync_project_tracks_to_recording_engine()
            self._refresh_active_project_playback_mix(f"track {track_index + 1} solo")
            self.refresh_track_list()

    def _set_track_armed(self, track_index: int, armed: bool) -> None:
        if track_index < 0 or track_index >= len(self.current_project.tracks):
            return
        track = self.current_project.tracks[track_index]
        track_type = self._normalize_track_type_label(getattr(track, "track_type", "Audio"))
        _expected_input_source, can_arm = self._track_runtime_policy(track_type)
        if armed and not can_arm:
            QMessageBox.information(
                self,
                "Recording",
                f"{track_type} tracks are playback/routing only in this build and cannot be record-armed.",
            )
            self.recording_controller.disarm_track(track_index)
            self.refresh_track_list()
            self.update_recording_status_label()
            self.update_status(f"Track {track_index + 1} remains disarmed ({track_type})")
            return
        if armed:
            if track_index not in self.recording_controller.armed_tracks:
                if not self.recording_controller.arm_track(track_index):
                    QMessageBox.warning(self, "Recording", self.recording_controller.status.last_error or "Could not arm track.")
        else:
            if track_index in self.recording_controller.armed_tracks:
                self.recording_controller.disarm_track(track_index)
        self.refresh_track_list()
        self.update_recording_status_label()
        self.update_status(f"Track {track_index + 1} {'armed' if track_index in self.recording_controller.armed_tracks else 'disarmed'}")

    def _rename_track_from_mixer(self, track_index: int, name: str) -> None:
        if track_index < 0 or track_index >= len(self.current_project.tracks):
            return
        cleaned_name = name.strip() or f"Track {track_index}"
        track = self.current_project.tracks[track_index]
        if track.name == cleaned_name:
            return
        pre_change_snapshot = self._snapshot_project_edit_state()
        track.name = cleaned_name
        self._push_project_snapshot(f"Rename track {track_index + 1}", pre_change_snapshot)
        self.sync_project_tracks_to_recording_engine()
        self.refresh_track_list()
        self.refresh_timeline()
        self.update_status(f"Renamed track {track_index} to {cleaned_name}")

    def _set_track_color(self, track_index: int, color_hex: str) -> None:
        if 0 <= track_index < len(self.current_project.tracks):
            track = self.current_project.tracks[track_index]
            next_color = color_hex or "#00F0FF"
            if str(getattr(track, "color_hex", "#00F0FF")) == next_color:
                return
            pre_change_snapshot = self._snapshot_project_edit_state()
            track.color_hex = next_color
            self._push_project_snapshot(f"Track {track_index + 1} color", pre_change_snapshot)
            self.refresh_timeline()

    def _set_track_input_source(self, track_index: int, input_source: str) -> None:
        if 0 <= track_index < len(self.current_project.tracks):
            track = self.current_project.tracks[track_index]
            track_type = self._normalize_track_type_label(getattr(track, "track_type", "Audio"))
            expected_input_source, _can_arm = self._track_runtime_policy(track_type)
            next_input_source = expected_input_source
            if track_type == "Audio":
                next_input_source = input_source or expected_input_source
            else:
                if input_source and input_source != expected_input_source:
                    self.update_status(
                        f"Track {track_index + 1} input locked to {expected_input_source} for {track_type} tracks"
                    )
                    self.refresh_track_list()
                    return
            current_input_source = str(getattr(track, "input_source", ""))
            if current_input_source == next_input_source:
                return
            pre_change_snapshot = self._snapshot_project_edit_state()
            track.input_source = next_input_source
            self._push_project_snapshot(f"Track {track_index + 1} input", pre_change_snapshot)
            self.update_status(f"Track {track_index + 1} input: {track.input_source}")

    def _count_enabled_track_effects(self, track: Track) -> int:
        effects = track.playback_settings.effects
        return int(bool(effects.echo_enabled)) + int(bool(effects.distortion_enabled)) + int(bool(effects.chorus_enabled))

    def _track_playback_summary(self, track: Track) -> tuple[str, str]:
        settings = track.playback_settings
        parts = []
        if settings.fade_in_ms > 0 or settings.fade_out_ms > 0:
            parts.append("FADE")
        if settings.loop_enabled:
            parts.append("LOOP")
        effect_count = self._count_enabled_track_effects(track)
        if effect_count > 0:
            parts.append(f"FX{effect_count}")
        summary = " | ".join(parts) if parts else "DRY"
        tooltip = (
            f"Fade in: {settings.fade_in_ms} ms\n"
            f"Fade out: {settings.fade_out_ms} ms\n"
            f"Loop: {'on' if settings.loop_enabled else 'off'}"
        )
        if settings.loop_enabled:
            tooltip += f" ({settings.loop_start_ms} ms -> {settings.loop_end_ms} ms)"
        tooltip += (
            f"\nEffects: echo={'on' if settings.effects.echo_enabled else 'off'}, "
            f"distortion={'on' if settings.effects.distortion_enabled else 'off'}, "
            f"chorus={'on' if settings.effects.chorus_enabled else 'off'}"
        )
        return summary, tooltip

    def _open_track_playback_settings(self, track_index: int) -> None:
        if not (0 <= track_index < len(self.current_project.tracks)):
            QMessageBox.warning(self, "Track settings", "Select a valid track first.")
            return

        track = self.current_project.tracks[track_index]
        dialog = TrackPlaybackSettingsDialog(track.name, track.playback_settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        updated_settings = dialog.get_settings()
        if updated_settings.loop_enabled and updated_settings.loop_end_ms <= updated_settings.loop_start_ms:
            QMessageBox.warning(self, "Track settings", "Loop end must be greater than loop start.")
            return

        track.playback_settings = updated_settings
        self.refresh_track_list()
        self.refresh_timeline()
        self._refresh_active_project_playback_mix(f"track {track_index + 1} playback settings")
        self.update_status(f"Updated playback settings for track {track_index + 1}")

    def refresh_track_list(self):
        super().refresh_track_list()
        self._rebuild_mixer_rows()
        self._refresh_single_track_editor()

    def open_voice_manager(self):
        super().open_voice_manager()
        if hasattr(self, "voice_profile_combo"):
            self._populate_voice_profile_combo()

    def refresh_recording_meters(self):
        super().refresh_recording_meters()
        levels = self.recording_controller.get_meter_levels()
        for track_id, row in enumerate(self.mixer_rows):
            track_levels = levels.get(track_id)
            if track_levels is not None:
                row.update_meter(track_levels["current_db"], track_levels["peak_db"])
        mixer_layout = getattr(self, "main_mixer_view", None)
        if self._is_project_playback_running():
            return
        if mixer_layout is not None and hasattr(mixer_layout, "update_master_levels"):
            mixer_layout.update_master_levels(levels, self.current_project.tracks)


EchoProWindow = TabbedEchoProWindow

# ── ENTRY POINT ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_common_validation_checks()
    app = QApplication(sys.argv)

    ensure_dirs()

    if is_first_run():
        dlg = FirstRunDialog()
        dlg.exec()
        mark_first_run_done()

    win = TabbedEchoProWindow()
    win.resize(1440, 900)
    win.show()
    sys.exit(app.exec())

