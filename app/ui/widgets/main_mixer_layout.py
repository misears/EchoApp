"""
Main Mixer / Arrangement View Layout

Implements the ergonomic layout skeleton per UX §1.9 & §2.1:
- Fixed-width left control zones (200px master, 220px channel strips)
- Flexible waveform/timeline area (grows with window)
- Fixed-width right sidebar (260px, collapsible)
- Transport bar (72px) and status bar (24px)
"""

import os
import json
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QToolBar, QScrollArea, QFrame, QToolButton, QMenu,
    QSizePolicy, QSpinBox, QDial, QComboBox, QMessageBox,
    QPushButton, QSlider, QTabWidget, QListWidget, QListWidgetItem,
    QInputDialog, QToolTip, QTreeWidget, QTreeWidgetItem, QLineEdit
)
from PySide6.QtCore import Qt, QSize, QSignalBlocker, QRect, QTimer, QEvent, QPoint
from PySide6.QtGui import QAction, QColor, QPainter, QPen, QCursor, QKeySequence
from typing import Optional
from app.controllers import TimelineSyncController
from app_paths import PROJECTS_DIR
from audio_info import get_audio_length_ms
from app.styles import C_CYAN, C_DIM, C_INPUT_BG, C_L0, C_L1, C_L2, C_L3, C_MUTED, C_TEXT
from .level_meter import VerticalLevelMeter


TIMELINE_PIXELS_PER_SECOND = 50.0
_AUDIO_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg", ".aif", ".aiff", ".m4a", ".aac"}


class BrowserTreeWidget(QTreeWidget):
    """Audio browser tree with external file-drop support."""

    def __init__(self, on_audio_files_dropped=None, parent=None):
        super().__init__(parent)
        self._on_audio_files_dropped = on_audio_files_dropped
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def _extract_audio_paths_from_mime(self, mime_data) -> list[Path]:
        if not mime_data.hasUrls():
            return []
        paths: list[Path] = []
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.lower() in _AUDIO_SUFFIXES:
                paths.append(path)
        return paths

    def dragEnterEvent(self, event) -> None:
        if self._extract_audio_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if self._extract_audio_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        dropped_paths = self._extract_audio_paths_from_mime(event.mimeData())
        if dropped_paths:
            if callable(self._on_audio_files_dropped):
                self._on_audio_files_dropped(dropped_paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)


class TimelineRulerCanvas(QWidget):
    def __init__(self, timeline_controller: Optional[TimelineSyncController] = None, parent=None):
        super().__init__(parent)
        self.timeline_controller = timeline_controller
        self._display_mode = "bars"
        self._zoom_factor = timeline_controller.get_zoom_factor() if timeline_controller else 1.0
        self._scroll_position_px = timeline_controller.get_scroll_position() if timeline_controller else 0
        self._playhead_ms = timeline_controller.get_playhead() if timeline_controller else 0
        self._bpm = timeline_controller.get_bpm() if timeline_controller else 120.0
        self._time_signature = timeline_controller.get_time_signature() if timeline_controller else "4/4"
        self._content_width_px = 1200
        self.setFixedHeight(28)
        self.setMinimumWidth(160)
        if self.timeline_controller is not None:
            self.timeline_controller.playhead_changed.connect(self._on_playhead_changed)
            self.timeline_controller.zoom_factor_changed.connect(self._on_zoom_changed)
            self.timeline_controller.scroll_position_changed.connect(self._on_scroll_changed)
            self.timeline_controller.bpm_changed.connect(self._on_bpm_changed)
            self.timeline_controller.time_signature_changed.connect(self._on_time_signature_changed)

    def set_content_width_px(self, width_px: int) -> None:
        self._content_width_px = max(self.width(), int(width_px))
        self.update()

    def set_display_mode(self, mode: str) -> None:
        self._display_mode = "seconds" if str(mode).strip().lower() == "seconds" else "bars"
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(C_L1))
        bottom = self.height() - 1
        painter.setPen(QPen(QColor(C_L3), 1))
        painter.drawLine(0, bottom, self.width(), bottom)

        if self._display_mode == "seconds":
            self._paint_seconds_ruler(painter)
        else:
            self._paint_bars_ruler(painter)

        playhead_x = self._ms_to_x(self._playhead_ms)
        if 0 <= playhead_x <= self.width():
            painter.setPen(QPen(QColor(C_CYAN), 2))
            painter.drawLine(playhead_x, 0, playhead_x, self.height())

        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.timeline_controller is not None:
            self.timeline_controller.set_playhead(self._x_to_ms(int(event.position().x())))
            return
        super().mousePressEvent(event)

    def _paint_seconds_ruler(self, painter) -> None:
        visible_seconds = max(1, int(self._visible_width_seconds()) + 2)
        start_second = max(0, int(self._scroll_position_px / self._pixels_per_second()))
        end_second = start_second + visible_seconds
        painter.setPen(QPen(QColor(C_MUTED), 1))
        for second in range(start_second, end_second + 1):
            x = self._ms_to_x(second * 1000)
            if x < 0 or x > self.width():
                continue
            major = (second % 5) == 0
            tick_top = 8 if major else 14
            painter.drawLine(x, tick_top, x, self.height() - 2)
            if major:
                painter.drawText(QRect(x + 4, 1, 54, 12), Qt.AlignmentFlag.AlignLeft, self._format_seconds(second))

    def _paint_bars_ruler(self, painter) -> None:
        numerator, denominator = self._time_signature_parts()
        beat_seconds = 60.0 / max(1.0, float(self._bpm))
        beats_per_bar = max(1, numerator)
        bar_seconds = beat_seconds * beats_per_bar * (4.0 / max(1, denominator))
        visible_bars = max(2, int(self._visible_width_seconds() / max(bar_seconds, 0.001)) + 3)
        start_bar = max(0, int(self._scroll_position_px / (self._pixels_per_second() * max(bar_seconds, 0.001))))
        painter.setPen(QPen(QColor(C_MUTED), 1))
        for bar_index in range(start_bar, start_bar + visible_bars):
            bar_start_ms = int(round(bar_index * bar_seconds * 1000.0))
            bar_x = self._ms_to_x(bar_start_ms)
            if -40 <= bar_x <= self.width():
                painter.drawLine(bar_x, 7, bar_x, self.height() - 2)
                painter.drawText(QRect(bar_x + 4, 1, 54, 12), Qt.AlignmentFlag.AlignLeft, f"{bar_index + 1}:1")
            for beat_index in range(1, beats_per_bar):
                beat_ms = int(round((bar_index * bar_seconds + beat_index * beat_seconds) * 1000.0))
                beat_x = self._ms_to_x(beat_ms)
                if 0 <= beat_x <= self.width():
                    painter.drawLine(beat_x, 13, beat_x, self.height() - 2)

    def _format_seconds(self, total_seconds: int) -> str:
        minutes, seconds = divmod(max(0, total_seconds), 60)
        return f"{minutes}:{seconds:02d}"

    def _pixels_per_second(self) -> float:
        return TIMELINE_PIXELS_PER_SECOND * max(0.125, float(self._zoom_factor))

    def _visible_width_seconds(self) -> float:
        return float(max(1, self.width())) / self._pixels_per_second()

    def _ms_to_x(self, ms: int) -> int:
        return int(round((float(ms) / 1000.0) * self._pixels_per_second() - float(self._scroll_position_px)))

    def _x_to_ms(self, x: int) -> int:
        max_px = max(0, int(self._content_width_px) - 1)
        absolute_px = min(max_px, max(0, int(x) + int(self._scroll_position_px)))
        seconds = float(absolute_px) / self._pixels_per_second()
        return int(round(seconds * 1000.0))

    def _time_signature_parts(self) -> tuple[int, int]:
        raw = str(self._time_signature or "4/4")
        left, _, right = raw.partition("/")
        try:
            return max(1, int(left)), max(1, int(right or "4"))
        except ValueError:
            return 4, 4

    def _on_playhead_changed(self, playhead_ms: int) -> None:
        self._playhead_ms = int(playhead_ms)
        self.update()

    def _on_zoom_changed(self, zoom_factor: float) -> None:
        self._zoom_factor = float(zoom_factor)
        self.update()

    def _on_scroll_changed(self, scroll_position_px: int) -> None:
        self._scroll_position_px = int(scroll_position_px)
        self.update()

    def _on_bpm_changed(self, bpm: float) -> None:
        self._bpm = float(bpm)
        self.update()

    def _on_time_signature_changed(self, signature: str) -> None:
        self._time_signature = signature
        self.update()


class MainMixerLayout(QWidget):
    """
    Implements the main mixer/arrangement view layout with fixed-width control zones.
    
    Integrates TimelineSyncController (Group 2.1) as single source of truth for all
    timeline state: playhead, zoom, scroll, playback, BPM, master volume.
    
    All UI zones (Ruler, Transport, Waveform, Master Section) subscribe to controller
    signals instead of managing state independently.
    
    Layout structure:
    ┌─────────────────────────────────────────┐
    │ Toolbar (File/Edit/View/Project/AI...) │
    ├─────────────────────────────────────────┤
    │ Timeline Ruler (28px)                   │
    ├──────────┬───────────────────┬──────────┤
    │ Master   │ Waveform Lanes    │ Sidebar  │
    │ (200px)  │ (flexible, grows) │ (260px)  │
    │ Section  │                   │ [collaps]│
    │          │                   │          │
    ├──────────┴───────────────────┴──────────┤
    │ Transport Bar (72px, full width)        │
    ├─────────────────────────────────────────┤
    │ Status Bar (24px, managed by QMainWin)  │
    └─────────────────────────────────────────┘
    """

    def __init__(self, timeline_controller: Optional[TimelineSyncController] = None, parent=None):
        super().__init__(parent)
        self.timeline_controller = timeline_controller
        self._toolbar_quick_buttons: dict[str, QToolButton] = {}
        self._dropped_browser_files: list[Path] = []
        self._syncing_mixer_seek_slider = False
        self._sessions_tooltip_timer = QTimer(self)
        self._sessions_tooltip_timer.setSingleShot(True)
        self._sessions_tooltip_timer.setInterval(500)
        self._sessions_tooltip_timer.timeout.connect(self._show_session_hover_tooltip)
        self._sessions_hover_item: Optional[QListWidgetItem] = None
        self._sidebar_collapsed = False
        self._timeline_content_width_px = 1200
        self._master_lufs_integrated_db = -70.0
        self._init_ui()
        self._connect_timeline_controller()

    def _init_ui(self) -> None:
        """Build the main mixer layout structure."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ─────────────────────────────────────────────────────────────────────
        # Toolbar (File/Edit/View/Project/AI Tools/Settings)
        # ─────────────────────────────────────────────────────────────────────
        toolbar = self._build_toolbar()
        root.addWidget(toolbar)

        # ─────────────────────────────────────────────────────────────────────
        # Timeline Ruler (28px, sticky top)
        # ─────────────────────────────────────────────────────────────────────
        timeline_ruler = self._build_timeline_ruler()
        root.addWidget(timeline_ruler)

        # ─────────────────────────────────────────────────────────────────────
        # Main Content Area: Master | Waveform | Sidebar (in horizontal splitter)
        # ─────────────────────────────────────────────────────────────────────
        self.content_splitter = self._build_content_area()
        root.addWidget(self.content_splitter, stretch=1)

        # ─────────────────────────────────────────────────────────────────────
        # Transport Bar (72px, full width, never resizes)
        # ─────────────────────────────────────────────────────────────────────
        # NOTE: Transport bar is managed by parent window; attach to this layout
        # when parent passes it during setup.
        self.transport_bar_container = QWidget()
        self.transport_bar_container.setFixedHeight(72)
        root.addWidget(self.transport_bar_container)

        # Status bar is managed by QMainWindow, no need to add here.

    def _build_toolbar(self) -> QToolBar:
        """Build the top toolbar with menus and action buttons."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setFixedHeight(48)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setStyleSheet(
            f"""
            QToolBar {{
                background-color: {C_L1};
                border-bottom: 1px solid {C_L3};
                spacing: 6px;
                padding: 4px 8px;
            }}
            QToolButton#ToolbarMenuButton,
            QToolButton#ToolbarQuickButton {{
                background-color: {C_L2};
                color: {C_TEXT};
                border: 1px solid {C_L3};
                border-radius: 4px;
                padding: 5px 10px;
            }}
            QToolButton#ToolbarMenuButton:hover,
            QToolButton#ToolbarQuickButton:hover {{
                border-color: {C_CYAN};
                color: #FFFFFF;
            }}
            QToolButton#ToolbarQuickButton {{
                min-width: 30px;
                max-width: 34px;
                min-height: 30px;
                max-height: 34px;
                padding: 0px;
                font-size: 13px;
                font-weight: bold;
            }}
            QToolButton#ToolbarQuickButton:disabled {{
                color: {C_DIM};
                border-color: {C_L3};
            }}
            QSpinBox, QComboBox {{
                min-height: 28px;
                background-color: {C_INPUT_BG};
                border: 1px solid {C_L3};
                color: {C_TEXT};
                padding: 3px 6px;
            }}
            QDial {{
                background-color: {C_L0};
            }}
            QLabel[toolbarRole='caption'] {{
                color: {C_MUTED};
                font-size: 10px;
                letter-spacing: 0.5px;
            }}
            QLabel[toolbarRole='readout'] {{
                color: {C_CYAN};
                font-size: 11px;
                font-family: Consolas;
            }}
            """
        )

        menu_specs = [
            ("File", [
                ("New Project", ("new_project",), True, "Ctrl+N"),
                ("Open Project...", ("open_project",), True, "Ctrl+O"),
                ("Save Project", ("save_project_dialog",), True, "Ctrl+S"),
                ("Export Mix...", ("export_project_mix_dialog",), True, "Ctrl+Shift+E"),
            ]),
            ("Edit", [
                ("Undo", ("undo_last_recording_take",), True, "Ctrl+Z"),
                ("Redo", ("redo_last_recording_take",), True, "Ctrl+Y"),
            ]),
            ("View", [
                ("Mixer", tuple(), True, None),
                ("Home", tuple(), True, None),
                ("Recording", tuple(), True, None),
                ("Toggle Sidebar", ("toggle_mixer_sidebar",), True, "Ctrl+B"),
            ]),
            ("Project", [
                ("Project Browser...", ("browse_projects",), True, None),
                ("New Track", ("add_track",), True, None),
            ]),
            ("AI Tools", [
                ("Stem Separation (Demucs)", tuple(), True, None),
                ("AI Generation (ACE-Step)", tuple(), True, None),
            ]),
            ("Settings", [
                ("Open Settings", ("open_app_settings_dialog",), True, "Ctrl+,"),
            ]),
        ]
        for title, entries in menu_specs:
            toolbar.addWidget(self._build_menu_button(title, entries))

        toolbar.addSeparator()

        quick_actions = [
            ("new", "＋", "New Project (Ctrl+N)", ("new_project",), True),
            ("open", "⭳", "Open Project (Ctrl+O)", ("open_project",), True),
            ("save", "💾", "Save Project (Ctrl+S)", ("save_project_dialog",), True),
            ("export", "⇪", "Export Mix (Ctrl+Shift+E)", ("export_project_mix_dialog",), True),
            ("undo", "↶", "Undo (Ctrl+Z)", ("undo_last_recording_take",), True),
            ("redo", "↷", "Redo (Ctrl+Y)", ("redo_last_recording_take",), True),
        ]
        for key, glyph, tooltip, slot_names, enabled in quick_actions:
            button = self._build_quick_button(glyph, tooltip, slot_names, enabled)
            self._toolbar_quick_buttons[key] = button
            toolbar.addWidget(button)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        bpm_label = QLabel("BPM")
        bpm_label.setProperty("toolbarRole", "caption")
        toolbar.addWidget(bpm_label)
        self.bpm_spinbox = QSpinBox()
        self.bpm_spinbox.setRange(30, 300)
        self.bpm_spinbox.setValue(int(self.timeline_controller.get_bpm()) if self.timeline_controller else 120)
        self.bpm_spinbox.setSuffix(" ")
        self.bpm_spinbox.setFixedWidth(72)
        self.bpm_spinbox.setToolTip("Project tempo. Mouse wheel nudges the BPM value.")
        self.bpm_spinbox.valueChanged.connect(self._on_bpm_changed)
        toolbar.addWidget(self.bpm_spinbox)

        time_sig_label = QLabel("Time")
        time_sig_label.setProperty("toolbarRole", "caption")
        toolbar.addWidget(time_sig_label)
        self.time_signature_combo = QComboBox()
        self.time_signature_combo.setFixedWidth(82)
        self.time_signature_combo.addItems(["4/4", "3/4", "6/8", "5/4", "Custom"])
        self.time_signature_combo.setCurrentText(
            self.timeline_controller.get_time_signature() if self.timeline_controller else "4/4"
        )
        self.time_signature_combo.setToolTip("Project time signature.")
        self.time_signature_combo.currentTextChanged.connect(self._on_time_signature_changed)
        toolbar.addWidget(self.time_signature_combo)

        volume_label = QLabel("Master")
        volume_label.setProperty("toolbarRole", "caption")
        toolbar.addWidget(volume_label)
        self.master_volume_dial = QDial()
        self.master_volume_dial.setFixedSize(32, 32)
        self.master_volume_dial.setRange(-80, 12)
        self.master_volume_dial.setNotchesVisible(True)
        self.master_volume_dial.setToolTip("Master output volume in dB.")
        self.master_volume_dial.valueChanged.connect(self._on_master_volume_changed)
        toolbar.addWidget(self.master_volume_dial)
        self.master_volume_value = QLabel("0 dB")
        self.master_volume_value.setProperty("toolbarRole", "readout")
        self.master_volume_value.setMinimumWidth(48)
        toolbar.addWidget(self.master_volume_value)

        sample_label = QLabel("Format")
        sample_label.setProperty("toolbarRole", "caption")
        toolbar.addWidget(sample_label)
        self.sample_format_label = QLabel(self._sample_format_text())
        self.sample_format_label.setProperty("toolbarRole", "readout")
        self.sample_format_label.setToolTip("Current sample rate and working bit depth readout.")
        toolbar.addWidget(self.sample_format_label)

        self._sync_master_volume_widget(int(self.timeline_controller.get_master_volume()) if self.timeline_controller else 0)
        
        return toolbar

    def _build_menu_button(
        self,
        title: str,
        entries: list[tuple[str, tuple[str, ...], bool, Optional[str]]],
    ) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("ToolbarMenuButton")
        button.setText(title)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(button)
        for label, slot_names, enabled, shortcut in entries:
            action = QAction(label, menu)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            if title == "View" and label in {"Mixer", "Home", "Recording"}:
                action.triggered.connect(lambda _=False, tab_name=label: self._activate_tab(tab_name))
            elif title == "AI Tools" and label == "Stem Separation (Demucs)":
                action.triggered.connect(lambda _=False: self._activate_tab("Tools"))
            elif title == "AI Tools" and label == "AI Generation (ACE-Step)":
                action.triggered.connect(lambda _=False: self._activate_tab("Music"))
            elif enabled:
                action.triggered.connect(lambda _=False, names=slot_names: self._invoke_window_slot(*names))
            else:
                action.triggered.connect(lambda _=False, text=label: self._show_unavailable(text))
            action.setEnabled(enabled)
            menu.addAction(action)
        button.setMenu(menu)
        return button

    def _build_quick_button(
        self,
        glyph: str,
        tooltip: str,
        slot_names: tuple[str, ...],
        enabled: bool,
    ) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("ToolbarQuickButton")
        button.setText(glyph)
        button.setToolTip(tooltip)
        button.setEnabled(enabled)
        if enabled:
            button.clicked.connect(lambda _=False, names=slot_names: self._invoke_window_slot(*names))
        return button

    def _connect_timeline_controller(self) -> None:
        if self.timeline_controller is None:
            return
        self.timeline_controller.bpm_changed.connect(self._sync_bpm_widget)
        self.timeline_controller.time_signature_changed.connect(self._sync_time_signature_widget)
        self.timeline_controller.master_volume_changed.connect(self._sync_master_volume_widget)
        self.timeline_controller.playhead_changed.connect(self._sync_mixer_transport_readouts)
        self.timeline_controller.bpm_changed.connect(self._sync_mixer_bpm_mirror)

    def _on_bpm_changed(self, value: int) -> None:
        if self.timeline_controller is not None:
            self.timeline_controller.set_bpm(float(value))

    def _on_time_signature_changed(self, signature: str) -> None:
        if signature == "Custom":
            self._show_unavailable("Custom time signatures")
            signature = self.timeline_controller.get_time_signature() if self.timeline_controller else "4/4"
            self._sync_time_signature_widget(signature)
            return
        if self.timeline_controller is not None:
            self.timeline_controller.set_time_signature(signature)

    def _on_master_volume_changed(self, value: int) -> None:
        self.master_volume_value.setText(f"{value:+d} dB" if value else "0 dB")
        if self.timeline_controller is not None:
            self.timeline_controller.set_master_volume(float(value))

    def _on_master_fader_changed(self, value: int) -> None:
        self._on_master_volume_changed(int(value))

    def _sync_bpm_widget(self, bpm: float) -> None:
        with QSignalBlocker(self.bpm_spinbox):
            self.bpm_spinbox.setValue(int(round(bpm)))

    def _sync_time_signature_widget(self, signature: str) -> None:
        with QSignalBlocker(self.time_signature_combo):
            index = self.time_signature_combo.findText(signature)
            if index >= 0:
                self.time_signature_combo.setCurrentIndex(index)
            else:
                self.time_signature_combo.setCurrentText("Custom")

    def _sync_master_volume_widget(self, volume_db: float) -> None:
        dial_value = int(round(volume_db))
        with QSignalBlocker(self.master_volume_dial):
            self.master_volume_dial.setValue(dial_value)
        if hasattr(self, "master_fader"):
            with QSignalBlocker(self.master_fader):
                self.master_fader.setValue(dial_value)
        self.master_volume_value.setText(f"{dial_value:+d} dB" if dial_value else "0 dB")
        if hasattr(self, "master_fader_value"):
            self.master_fader_value.setText(f"{dial_value:+d} dB" if dial_value else "0 dB")

    def _activate_tab(self, tab_name: str) -> None:
        window = self.window()
        tabs = getattr(window, "tabs", None)
        if tabs is None:
            self._show_unavailable(tab_name)
            return
        for index in range(tabs.count()):
            if tabs.tabText(index) == tab_name:
                tabs.setCurrentIndex(index)
                if hasattr(window, "update_status"):
                    window.update_status(f"Switched to {tab_name} tab")
                return
        self._show_unavailable(tab_name)

    def _invoke_window_slot(self, *slot_names: str) -> None:
        window = self.window()
        for slot_name in slot_names:
            callback = getattr(window, slot_name, None)
            if callable(callback):
                callback()
                return
        self._show_unavailable(slot_names[0] if slot_names else "Requested action")

    def _show_unavailable(self, feature_name: str) -> None:
        window = self.window()
        message = f"{feature_name} is not wired yet in the active Mixer view."
        if hasattr(window, "update_status"):
            window.update_status(message)
            return
        QMessageBox.information(self, "Not available yet", message)

    def _sample_format_text(self) -> str:
        window = self.window()
        sample_rate = None
        sample_rate_combo = getattr(window, "sample_rate_combo", None)
        if sample_rate_combo is not None:
            sample_rate = sample_rate_combo.currentData() or sample_rate_combo.currentText()
        if sample_rate is None and self.timeline_controller is not None:
            sample_rate = getattr(self.timeline_controller, "_sample_rate", 44100)
        try:
            sample_rate_value = int(sample_rate)
        except (TypeError, ValueError):
            sample_rate_value = 44100
        return f"{sample_rate_value / 1000:.1f} kHz / 24-bit"

    def _build_timeline_ruler(self) -> QWidget:
        """Build the timeline ruler widget (28px height)."""
        ruler_widget = QFrame()
        ruler_widget.setFixedHeight(28)
        ruler_widget.setStyleSheet(
            f"QFrame {{ background-color: {C_L1}; border-bottom: 1px solid {C_L3}; }}"
        )
        layout = QHBoxLayout(ruler_widget)
        layout.setContentsMargins(200, 0, 260, 0)
        layout.setSpacing(6)

        self.ruler_mode_button = QToolButton(ruler_widget)
        self.ruler_mode_button.setText("Bars:Beats")
        self.ruler_mode_button.setFixedSize(78, 22)
        self.ruler_mode_button.setToolTip("Toggle the timeline ruler between Bars:Beats and Seconds.")
        self.ruler_mode_button.clicked.connect(self._toggle_ruler_mode)
        layout.addWidget(self.ruler_mode_button)

        self.timeline_ruler_canvas = TimelineRulerCanvas(self.timeline_controller, ruler_widget)
        self.timeline_ruler_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.timeline_ruler_canvas.set_content_width_px(self._timeline_content_width_px)
        layout.addWidget(self.timeline_ruler_canvas, stretch=1)
        
        return ruler_widget

    def _toggle_ruler_mode(self) -> None:
        current_text = self.ruler_mode_button.text()
        next_mode = "Seconds" if current_text == "Bars:Beats" else "Bars:Beats"
        self.ruler_mode_button.setText(next_mode)
        if hasattr(self, "timeline_ruler_canvas"):
            self.timeline_ruler_canvas.set_display_mode("seconds" if next_mode == "Seconds" else "bars")

    def _build_content_area(self) -> QSplitter:
        """
        Build the main content area with three zones:
        1. Left: Master Section (200px fixed)
        2. Center: Waveform Lanes (flexible, grows)
        3. Right: Sidebar (260px fixed, collapsible)
        """
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle { background: #1A1A1E; width: 2px; }"
        )

        # ─────────────────────────────────────────────────────────────────────
        # LEFT: Master Section (200px fixed)
        # ─────────────────────────────────────────────────────────────────────
        master_section = self._build_master_section()
        self.master_section = master_section
        splitter.addWidget(master_section)

        # ─────────────────────────────────────────────────────────────────────
        # CENTER: Waveform Lanes Container (flexible, stretch=1)
        # ─────────────────────────────────────────────────────────────────────
        waveform_area = self._build_waveform_area()
        self.waveform_area = waveform_area
        splitter.addWidget(waveform_area)

        # ─────────────────────────────────────────────────────────────────────
        # RIGHT: Sidebar (260px fixed, collapsible)
        # ─────────────────────────────────────────────────────────────────────
        sidebar = self._build_sidebar()
        self.sidebar_panel = sidebar
        splitter.addWidget(sidebar)

        # Set initial sizes: master=200, waveform=1000, sidebar=260
        # The middle (waveform) will expand when window is resized
        splitter.setSizes([200, 1000, 260])
        splitter.setStretchFactor(0, 0)  # Master: no stretch
        splitter.setStretchFactor(1, 1)  # Waveform: stretch to fill
        splitter.setStretchFactor(2, 0)  # Sidebar: no stretch
        
        # Prevent collapsing of fixed zones
        splitter.setCollapsible(0, False)  # Master always visible
        splitter.setCollapsible(1, False)  # Waveform always visible
        splitter.setCollapsible(2, True)   # Sidebar can collapse

        return splitter

    def toggle_sidebar(self) -> None:
        if not hasattr(self, "content_splitter") or not hasattr(self, "sidebar_panel"):
            return
        if self._sidebar_collapsed:
            self.sidebar_panel.setFixedWidth(260)
            self.content_splitter.setSizes([200, 1000, 260])
            self._sidebar_collapsed = False
            return
        self.sidebar_panel.setFixedWidth(0)
        self.content_splitter.setSizes([200, 1260, 0])
        self._sidebar_collapsed = True

    def _build_master_section(self) -> QWidget:
        """Build the left master section (200px fixed width)."""
        master = QFrame()
        master.setFixedWidth(200)
        master.setStyleSheet(
            f"""
            QFrame {{ background-color: {C_L2}; border-right: 1px solid {C_L3}; }}
            QLabel[masterRole='title'] {{
                color: {C_DIM};
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
            QLabel[masterRole='lufs'] {{
                color: {C_CYAN};
                font-size: 13px;
                font-family: Consolas;
            }}
            QLabel[masterRole='caption'] {{
                color: {C_MUTED};
                font-size: 10px;
            }}
            """
        )
        layout = QVBoxLayout(master)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("MASTER")
        title.setProperty("masterRole", "title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        meter_strip = QHBoxLayout()
        meter_strip.setContentsMargins(4, 6, 4, 0)
        meter_strip.setSpacing(8)

        fader_column = QVBoxLayout()
        fader_column.setSpacing(4)
        self.master_fader_value = QLabel("0 dB")
        self.master_fader_value.setProperty("masterRole", "lufs")
        self.master_fader_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fader_column.addWidget(self.master_fader_value)

        self.master_fader = QSlider(Qt.Orientation.Vertical)
        self.master_fader.setRange(-80, 12)
        self.master_fader.setValue(int(self.timeline_controller.get_master_volume()) if self.timeline_controller else 0)
        self.master_fader.setMinimumHeight(220)
        self.master_fader.setToolTip("Master output fader.")
        self.master_fader.valueChanged.connect(self._on_master_fader_changed)
        fader_column.addWidget(self.master_fader, alignment=Qt.AlignmentFlag.AlignHCenter)

        fader_caption = QLabel("FADER")
        fader_caption.setProperty("masterRole", "caption")
        fader_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fader_column.addWidget(fader_caption)
        meter_strip.addLayout(fader_column, stretch=1)

        vu_column = QVBoxLayout()
        vu_column.setSpacing(4)
        vu_title = QLabel("VU")
        vu_title.setProperty("masterRole", "caption")
        vu_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vu_column.addWidget(vu_title)

        vu_row = QHBoxLayout()
        vu_row.setSpacing(4)
        self.master_meter_left = VerticalLevelMeter()
        self.master_meter_left.setMinimumHeight(220)
        self.master_meter_right = VerticalLevelMeter()
        self.master_meter_right.setMinimumHeight(220)
        vu_row.addWidget(self.master_meter_left)
        vu_row.addWidget(self.master_meter_right)
        vu_column.addLayout(vu_row)

        vu_labels = QHBoxLayout()
        vu_labels.setSpacing(10)
        for label_text in ("L", "R"):
            label = QLabel(label_text)
            label.setProperty("masterRole", "caption")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vu_labels.addWidget(label)
        vu_column.addLayout(vu_labels)
        meter_strip.addLayout(vu_column, stretch=0)

        layout.addLayout(meter_strip)

        lufs_caption = QLabel("Integrated LUFS")
        lufs_caption.setProperty("masterRole", "caption")
        layout.addWidget(lufs_caption)

        self.master_lufs_value = QLabel("-14.0 LUFS")
        self.master_lufs_value.setProperty("masterRole", "lufs")
        layout.addWidget(self.master_lufs_value)

        peak_caption = QLabel("Peaks")
        peak_caption.setProperty("masterRole", "caption")
        layout.addWidget(peak_caption)

        peak_row = QHBoxLayout()
        peak_row.setSpacing(8)
        self.master_peak_left_value = QLabel("L -∞ dB")
        self.master_peak_left_value.setProperty("masterRole", "caption")
        self.master_peak_right_value = QLabel("R -∞ dB")
        self.master_peak_right_value.setProperty("masterRole", "caption")
        peak_row.addWidget(self.master_peak_left_value)
        peak_row.addWidget(self.master_peak_right_value)
        layout.addLayout(peak_row)

        waveform_caption = QLabel("Master Wave")
        waveform_caption.setProperty("masterRole", "caption")
        layout.addWidget(waveform_caption)

        self.master_waveform_preview = QLabel("▁▁▁▁▁▁▁▁▁▁▁▁")
        self.master_waveform_preview.setProperty("masterRole", "lufs")
        self.master_waveform_preview.setStyleSheet(f"color: {C_TEXT}; font-family: Consolas;")
        layout.addWidget(self.master_waveform_preview)

        self.master_eq_button = QPushButton("Master EQ")
        self.master_eq_button.setCheckable(True)
        self.master_eq_button.setToolTip("Enable or bypass the master EQ stage.")
        layout.addWidget(self.master_eq_button)

        limiter_row = QHBoxLayout()
        limiter_row.setSpacing(8)
        self.master_limiter_dial = QDial()
        self.master_limiter_dial.setRange(-24, 0)
        self.master_limiter_dial.setValue(-3)
        self.master_limiter_dial.setNotchesVisible(True)
        self.master_limiter_dial.setFixedSize(44, 44)
        self.master_limiter_dial.setToolTip("Master limiter threshold.")
        limiter_row.addWidget(self.master_limiter_dial)

        limiter_labels = QVBoxLayout()
        limiter_labels.setSpacing(2)
        limiter_title = QLabel("Limiter")
        limiter_title.setProperty("masterRole", "caption")
        limiter_labels.addWidget(limiter_title)
        self.master_limiter_value = QLabel("-3 dB")
        self.master_limiter_value.setProperty("masterRole", "lufs")
        limiter_labels.addWidget(self.master_limiter_value)
        limiter_row.addLayout(limiter_labels)
        limiter_row.addStretch()
        layout.addLayout(limiter_row)

        self.master_limiter_dial.valueChanged.connect(self._on_master_limiter_changed)

        self.master_fx_button = QPushButton("Effects Chain")
        self.master_fx_button.setToolTip("Open the master effects chain.")
        layout.addWidget(self.master_fx_button)

        self.master_eq_button.clicked.connect(self._on_master_eq_toggled)
        self.master_fx_button.clicked.connect(self._on_master_fx_clicked)

        self.master_meter_left.set_db(-60.0)
        self.master_meter_right.set_db(-60.0)
        self._sync_master_processing_from_window()

        layout.addStretch()
        return master

    def _build_waveform_area(self) -> QWidget:
        """
        Build the center waveform lanes area (flexible width, grows with window).
        This is where the timeline and track waveforms are displayed.
        """
        waveform = QFrame()
        waveform.setStyleSheet(
            "QFrame { background-color: #121214; }"
        )
        layout = QVBoxLayout(waveform)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # Placeholder for timeline/waveform widget
        placeholder = QLabel(
            "Waveform Lanes Area\n"
            "(Per-track color fill, clip rectangles, automation curves, magenta slice markers)"
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #6A6A73; font-size: 11px;")
        layout.addWidget(placeholder)
        self.waveform_placeholder = placeholder

        # TODO: Wire in TimelineWidget here
        # TODO: Display per-track waveforms with color fill
        # TODO: Show clip rectangles with labels
        # TODO: Display automation curve overlays (cyan with dot handles)
        # TODO: Show magenta slice markers

        return waveform

    def _build_sidebar(self) -> QWidget:
        """Build the right sidebar (260px fixed width, collapsible)."""
        sidebar = QFrame()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet(
            "QFrame { background-color: #1E1E22; border-left: 1px solid #2D2D32; }"
        )
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Sidebar tabs: Browser and Sessions
        title = QLabel("BROWSER / SESSIONS")
        title.setStyleSheet(
            "color: #6A6A73; font-size: 10px; font-weight: bold; letter-spacing: 1px;"
        )
        layout.addWidget(title)

        tabs = QTabWidget(sidebar)
        tabs.setDocumentMode(True)
        tabs.setStyleSheet(
            "QTabWidget::pane { border:1px solid #2D2D32; background:#16161A; }"
            "QTabBar::tab { background:#1E1E22; color:#AAB4BE; padding:4px 10px; border:1px solid #2D2D32; }"
            "QTabBar::tab:selected { color:#E2E2E5; border-color:#74C7FF; }"
        )

        browser_tab = QWidget()
        browser_layout = QVBoxLayout(browser_tab)
        browser_layout.setContentsMargins(8, 8, 8, 8)
        browser_layout.setSpacing(6)
        browser_controls = QHBoxLayout()
        browser_controls.setSpacing(6)
        browser_refresh = QPushButton("Refresh")
        browser_refresh.setToolTip("Refresh browser entries from current project and project library audio files.")
        browser_refresh.clicked.connect(self._populate_browser_tree)
        browser_controls.addWidget(browser_refresh)
        browser_controls.addStretch()
        browser_layout.addLayout(browser_controls)

        self.browser_tree = BrowserTreeWidget(self._on_browser_audio_files_dropped, browser_tab)
        self.browser_tree.setHeaderHidden(True)
        self.browser_tree.setAlternatingRowColors(False)
        self.browser_tree.setMouseTracking(True)
        self.browser_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.browser_tree.customContextMenuRequested.connect(self._show_browser_context_menu)
        self.browser_tree.itemDoubleClicked.connect(self._on_browser_item_activated)
        self.browser_tree.setStyleSheet(
            "QTreeWidget { background:#121418; border:1px solid #2D2D32; color:#D7DEE6; }"
            "QTreeView::item { padding:5px 6px; }"
            "QTreeView::item:selected { background:#1B2A3A; color:#FFFFFF; }"
        )
        browser_layout.addWidget(self.browser_tree)

        browser_hint = QLabel("Double-click an audio file to add it at the current playhead.")
        browser_hint.setWordWrap(True)
        browser_hint.setStyleSheet("color:#88929d; font-size:10px;")
        browser_layout.addWidget(browser_hint)

        sessions_tab = QWidget()
        sessions_layout = QVBoxLayout(sessions_tab)
        sessions_layout.setContentsMargins(6, 6, 6, 6)
        sessions_layout.setSpacing(6)

        self.sessions_list = QListWidget(sessions_tab)
        self.sessions_list.setMouseTracking(True)
        self.sessions_list.setUniformItemSizes(True)
        self.sessions_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sessions_list.customContextMenuRequested.connect(self._show_session_context_menu)
        self.sessions_list.viewport().installEventFilter(self)
        self.sessions_list.setStyleSheet(
            "QListWidget { background:#121418; border:1px solid #2D2D32; color:#D7DEE6; }"
            "QListWidget::item { border-bottom:1px solid #232830; padding:8px 8px; }"
            "QListWidget::item:selected { background:#1B2A3A; color:#FFFFFF; }"
        )
        sessions_layout.addWidget(self.sessions_list)

        tabs.addTab(browser_tab, "Browser")
        tabs.addTab(sessions_tab, "Sessions")
        layout.addWidget(tabs, stretch=1)

        self._populate_browser_tree()
        self._populate_sessions_list()

        layout.addStretch()
        return sidebar

    def _populate_sessions_list(self) -> None:
        if not hasattr(self, "sessions_list"):
            return
        self.sessions_list.clear()

        entries: list[str] = []
        window = self.window()
        recording_controller = getattr(window, "recording_controller", None)
        if recording_controller is not None:
            session = getattr(recording_controller, "session", None)
            if session is not None:
                session_id = str(getattr(session, "session_id", "current_session") or "current_session")
                project_name = str(getattr(session, "project_name", "Untitled") or "Untitled")
                entries.append(f"Current Session - {project_name} ({session_id})")

        if not entries:
            entries.append("Current Session - Untitled (default_session)")
        entries.extend([
            "Session Archive - Vocal Comping Review From Rehearsal Night 2026-07-18",
            "Session Archive - Alternate Chorus Takes And Stem Notes",
        ])

        for text in entries:
            item = QListWidgetItem(text)
            item.setToolTip(text)
            item.setSizeHint(QSize(0, 42))
            self.sessions_list.addItem(item)

    def _audio_metadata_text(self, file_path: Path) -> str:
        duration_text = "Unknown"
        sample_rate_text = "Unknown"
        try:
            length_ms = max(0, int(get_audio_length_ms(str(file_path))))
            duration_text = f"{length_ms / 1000.0:.2f}s"
        except Exception:
            duration_text = "Unknown"

        sample_rate_hz = self._probe_sample_rate_hz(file_path)
        if sample_rate_hz is not None and sample_rate_hz > 0:
            sample_rate_text = f"{int(sample_rate_hz)} Hz"

        return (
            f"Name: {file_path.name}\n"
            f"Duration: {duration_text}\n"
            f"Sample rate: {sample_rate_text}\n"
            f"Path: {file_path}"
        )

    def _probe_sample_rate_hz(self, file_path: Path) -> Optional[int]:
        try:
            import soundfile as sf
            info = sf.info(str(file_path))
            samplerate = int(getattr(info, "samplerate", 0) or 0)
            if samplerate > 0:
                return samplerate
        except Exception:
            pass

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "a:0",
                    "-show_entries",
                    "stream=sample_rate",
                    "-of",
                    "json",
                    str(file_path),
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=20,
            )
            payload = json.loads(result.stdout)
            streams = payload.get("streams") or []
            if streams:
                value = int(streams[0].get("sample_rate") or 0)
                if value > 0:
                    return value
        except Exception:
            return None
        return None

    def _create_browser_file_item(self, parent: QTreeWidgetItem, file_path: Path) -> None:
        item = QTreeWidgetItem(parent)
        item.setText(0, file_path.name)
        item.setData(0, Qt.ItemDataRole.UserRole, str(file_path))
        item.setToolTip(0, self._audio_metadata_text(file_path))

    def _populate_browser_tree(self) -> None:
        if not hasattr(self, "browser_tree"):
            return
        self.browser_tree.clear()

        window = self.window()
        current_root = QTreeWidgetItem(self.browser_tree)
        current_root.setText(0, "Current Project Audio")

        current_paths: list[Path] = []
        project = getattr(window, "current_project", None)
        if project is not None:
            for clip in getattr(project, "clips", []):
                path = Path(str(getattr(clip, "file_path", "") or ""))
                if path.exists() and path.suffix.lower() in _AUDIO_SUFFIXES:
                    current_paths.append(path)
        unique_current = sorted({p.resolve() for p in current_paths}, key=lambda p: p.name.lower())
        if unique_current:
            for path in unique_current[:120]:
                self._create_browser_file_item(current_root, path)
        else:
            empty_item = QTreeWidgetItem(current_root)
            empty_item.setText(0, "No project audio clips yet")
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)

        library_root = QTreeWidgetItem(self.browser_tree)
        library_root.setText(0, "Project Library")
        library_files: list[Path] = []
        if PROJECTS_DIR.exists():
            for candidate in PROJECTS_DIR.rglob("*"):
                if candidate.is_file() and candidate.suffix.lower() in _AUDIO_SUFFIXES:
                    library_files.append(candidate)
                if len(library_files) >= 200:
                    break
        if library_files:
            for path in sorted(library_files, key=lambda p: p.name.lower()):
                self._create_browser_file_item(library_root, path)
        else:
            empty_item = QTreeWidgetItem(library_root)
            empty_item.setText(0, "No library audio found")
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)

        dropped_files = [path for path in self._dropped_browser_files if path.exists() and path.is_file()]
        self._dropped_browser_files = dropped_files
        dropped_root = QTreeWidgetItem(self.browser_tree)
        dropped_root.setText(0, "Dropped Files")
        if dropped_files:
            for path in sorted(dropped_files, key=lambda p: p.name.lower()):
                self._create_browser_file_item(dropped_root, path)
        else:
            empty_item = QTreeWidgetItem(dropped_root)
            empty_item.setText(0, "Drop audio files here from Explorer")
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)

        self.browser_tree.expandToDepth(0)

    def _on_browser_audio_files_dropped(self, file_paths: list[Path]) -> None:
        cleaned_paths: list[Path] = []
        for path in file_paths:
            resolved = Path(path)
            if resolved.exists() and resolved.is_file() and resolved.suffix.lower() in _AUDIO_SUFFIXES:
                cleaned_paths.append(resolved)
        if not cleaned_paths:
            self._show_unavailable("Dropped files are not supported audio formats")
            return

        for path in cleaned_paths:
            if path not in self._dropped_browser_files:
                self._dropped_browser_files.append(path)

        mode, accepted = QInputDialog.getItem(
            self,
            "Import Dropped Audio",
            "Add dropped files to",
            ["Selected Track", "New Audio Track"],
            current=0,
            editable=False,
        )
        if not accepted:
            self._populate_browser_tree()
            return

        create_new_track = str(mode) == "New Audio Track"
        first = True
        added_count = 0
        for path in cleaned_paths:
            add_to_new_track = bool(create_new_track and first)
            if self._request_add_browser_audio(path, create_new_track=add_to_new_track):
                added_count += 1
            first = False

        self._populate_browser_tree()
        if added_count > 0:
            window = self.window()
            if hasattr(window, "update_status"):
                window.update_status(f"Imported {added_count} dropped browser file(s)")

    def _browser_item_path(self, item: Optional[QTreeWidgetItem]) -> Optional[Path]:
        if item is None:
            return None
        raw_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not raw_path:
            return None
        path = Path(str(raw_path))
        return path if path.exists() else None

    def _request_add_browser_audio(self, file_path: Path, *, create_new_track: bool = False) -> bool:
        window = self.window()
        callback = getattr(window, "add_clip_from_browser_path", None)
        if callable(callback):
            return bool(callback(file_path, create_new_track=create_new_track))
        self._show_unavailable("Browser clip add")
        return False

    def _on_browser_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        file_path = self._browser_item_path(item)
        if file_path is None:
            return
        self._request_add_browser_audio(file_path, create_new_track=False)

    def _show_browser_context_menu(self, position: QPoint) -> None:
        if not hasattr(self, "browser_tree"):
            return
        item = self.browser_tree.itemAt(position)
        file_path = self._browser_item_path(item)

        menu = QMenu(self)
        refresh_action = menu.addAction("Refresh Browser")
        add_selected_action = None
        add_new_track_action = None
        reveal_action = None
        if file_path is not None:
            add_selected_action = menu.addAction("Add to Selected Track")
            add_new_track_action = menu.addAction("Add to New Audio Track")
            reveal_action = menu.addAction("Reveal in Folder")

        selected_action = menu.exec(self.browser_tree.viewport().mapToGlobal(position))
        if selected_action is None:
            return
        if selected_action is refresh_action:
            self._populate_browser_tree()
            return
        if file_path is None:
            return
        if selected_action is add_selected_action:
            self._request_add_browser_audio(file_path, create_new_track=False)
            return
        if selected_action is add_new_track_action:
            self._request_add_browser_audio(file_path, create_new_track=True)
            return
        if selected_action is reveal_action:
            try:
                if os.name == "nt":
                    os.startfile(str(file_path.parent))
                else:
                    self._show_unavailable("Reveal in folder")
            except Exception:
                self._show_unavailable("Reveal in folder")

    def _show_session_context_menu(self, position: QPoint) -> None:
        if not hasattr(self, "sessions_list"):
            return
        item = self.sessions_list.itemAt(position)
        if item is None:
            return

        menu = QMenu(self)
        open_action = menu.addAction("Open Session")
        rename_action = menu.addAction("Rename Session")
        duplicate_action = menu.addAction("Duplicate Session")
        delete_action = menu.addAction("Delete Session")

        selected_action = menu.exec(self.sessions_list.viewport().mapToGlobal(position))
        if selected_action is None:
            return
        if selected_action is open_action:
            self._show_unavailable(f"Open Session: {item.text()}")
            return
        if selected_action is rename_action:
            updated_name, accepted = QInputDialog.getText(self, "Rename Session", "Session name", text=item.text())
            if accepted and updated_name.strip():
                item.setText(updated_name.strip())
                item.setToolTip(updated_name.strip())
            return
        if selected_action is duplicate_action:
            copied = QListWidgetItem(f"{item.text()} (Copy)")
            copied.setToolTip(copied.text())
            copied.setSizeHint(QSize(0, 42))
            insert_index = self.sessions_list.row(item) + 1
            self.sessions_list.insertItem(insert_index, copied)
            return
        if selected_action is delete_action:
            response = QMessageBox.question(
                self,
                "Delete Session",
                f"Remove '{item.text()}' from the Sessions list?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if response == QMessageBox.StandardButton.Yes:
                self.sessions_list.takeItem(self.sessions_list.row(item))

    def eventFilter(self, watched, event):
        if hasattr(self, "sessions_list") and watched is self.sessions_list.viewport():
            if event.type() == QEvent.Type.Leave:
                self._sessions_tooltip_timer.stop()
                self._sessions_hover_item = None
                QToolTip.hideText()
                return False

            if event.type() == QEvent.Type.MouseMove:
                item = self.sessions_list.itemAt(event.position().toPoint())
                if item is not self._sessions_hover_item:
                    self._sessions_tooltip_timer.stop()
                    QToolTip.hideText()
                    self._sessions_hover_item = item
                    if item is not None and self._session_name_is_truncated(item.text()):
                        self._sessions_tooltip_timer.start()
                return False

        return super().eventFilter(watched, event)

    def _session_name_is_truncated(self, text: str) -> bool:
        if not hasattr(self, "sessions_list"):
            return False
        width = max(1, self.sessions_list.viewport().width() - 18)
        return self.sessions_list.fontMetrics().horizontalAdvance(text) > width

    def _show_session_hover_tooltip(self) -> None:
        item = self._sessions_hover_item
        if not hasattr(self, "sessions_list") or item is None:
            return
        if not self._session_name_is_truncated(item.text()):
            return
        item_rect = self.sessions_list.visualItemRect(item)
        anchor = self.sessions_list.viewport().mapToGlobal(item_rect.bottomLeft())
        QToolTip.showText(anchor, item.text(), self.sessions_list)

    def _on_master_eq_toggled(self, enabled: bool) -> None:
        window = self.window()
        callback = getattr(window, "set_master_eq_enabled", None)
        if callable(callback):
            callback(bool(enabled))
            return
        if hasattr(window, "update_status"):
            window.update_status(f"Master EQ {'enabled' if enabled else 'bypassed'}")

    def _on_master_fx_clicked(self) -> None:
        window = self.window()
        callback = getattr(window, "open_master_effects_chain", None)
        if callable(callback):
            callback()
            return
        self._show_unavailable("Master effects chain")

    def _on_master_limiter_changed(self, value: int) -> None:
        limiter_db = int(value)
        self.master_limiter_value.setText(f"{limiter_db} dB")
        window = self.window()
        callback = getattr(window, "set_master_limiter_threshold_db", None)
        if callable(callback):
            callback(limiter_db)

    def _sync_master_processing_from_window(self) -> None:
        window = self.window()
        metadata = getattr(getattr(window, "current_project", None), "metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        eq_enabled = bool(metadata.get("master_eq_enabled", False))
        limiter_db = int(metadata.get("master_limiter_threshold_db", -3))
        limiter_db = max(-24, min(0, limiter_db))

        self.master_eq_button.blockSignals(True)
        self.master_eq_button.setChecked(eq_enabled)
        self.master_eq_button.blockSignals(False)

        self.master_limiter_dial.blockSignals(True)
        self.master_limiter_dial.setValue(limiter_db)
        self.master_limiter_dial.blockSignals(False)
        self.master_limiter_value.setText(f"{limiter_db} dB")

    def update_master_levels(self, levels_by_track: dict, tracks: list) -> None:
        if not isinstance(levels_by_track, dict) or not tracks:
            self.master_meter_left.set_db(-60.0)
            self.master_meter_right.set_db(-60.0)
            self.master_lufs_value.setText("-70.0 LUFS-I")
            self.master_peak_left_value.setText("L -∞ dB")
            self.master_peak_right_value.setText("R -∞ dB")
            self.master_waveform_preview.setText("▁▁▁▁▁▁▁▁▁▁▁▁")
            return

        any_solo = any(bool(getattr(track, "soloed", False)) for track in tracks)
        summed_linear = 0.0
        for index, track in enumerate(tracks):
            if bool(getattr(track, "muted", False)):
                continue
            if any_solo and not bool(getattr(track, "soloed", False)):
                continue
            level_info = levels_by_track.get(index)
            if not isinstance(level_info, dict):
                continue
            track_db = float(level_info.get("current_db", -80.0)) + float(getattr(track, "volume_db", 0.0))
            summed_linear += 10.0 ** (track_db / 20.0)

        if summed_linear <= 1e-6:
            current_db = -60.0
        else:
            import math
            current_db = max(-60.0, min(6.0, 20.0 * math.log10(summed_linear)))

        self.master_meter_left.set_db(current_db)
        self.master_meter_right.set_db(current_db)

        # DAW-style integrated loudness proxy with strong smoothing.
        alpha = 0.985
        self._master_lufs_integrated_db = (alpha * float(self._master_lufs_integrated_db)) + ((1.0 - alpha) * float(current_db))
        display_lufs = max(-70.0, min(3.0, self._master_lufs_integrated_db - 0.8))
        self.master_lufs_value.setText(f"{display_lufs:.1f} LUFS-I")
        self.master_peak_left_value.setText(f"L {current_db:+.1f} dB")
        self.master_peak_right_value.setText(f"R {current_db:+.1f} dB")

    def update_master_playback_metrics(
        self,
        *,
        left_db: float,
        right_db: float,
        peak_left_db: float,
        peak_right_db: float,
        lufs_integrated_db: float,
        waveform_preview: str,
    ) -> None:
        self.master_meter_left.set_db(float(left_db))
        self.master_meter_right.set_db(float(right_db))
        self.master_lufs_value.setText(f"{float(lufs_integrated_db):.1f} LUFS-I")
        self.master_peak_left_value.setText(f"L {float(peak_left_db):+.1f} dB")
        self.master_peak_right_value.setText(f"R {float(peak_right_db):+.1f} dB")
        self.master_waveform_preview.setText(str(waveform_preview))

    def reset_master_playback_metrics(self) -> None:
        self.master_meter_left.set_db(-60.0)
        self.master_meter_right.set_db(-60.0)
        self.master_lufs_value.setText("-70.0 LUFS-I")
        self.master_peak_left_value.setText("L -∞ dB")
        self.master_peak_right_value.setText("R -∞ dB")
        self.master_waveform_preview.setText("▁▁▁▁▁▁▁▁▁▁▁▁")

    def set_timeline_content_width(self, width_px: int) -> None:
        self._timeline_content_width_px = max(1200, int(width_px))
        if hasattr(self, "timeline_ruler_canvas"):
            self.timeline_ruler_canvas.set_content_width_px(self._timeline_content_width_px)

    def set_transport_bar(self, transport_bar_widget: QWidget) -> None:
        """
        Attach the transport bar to this mixer layout.
        Called by parent window after transport bar is created.
        """
        layout = self.transport_bar_container.layout()
        if layout is None:
            layout = QVBoxLayout(self.transport_bar_container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            self.transport_bar_container.setLayout(layout)

        while layout.count() > 0:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        shell = QFrame(self.transport_bar_container)
        shell.setObjectName("MixerTransportShell")
        shell.setFixedHeight(72)
        shell.setStyleSheet(
            "QFrame#MixerTransportShell { background:#171a1f; border-top:1px solid #2D2D32; }"
            "QLabel[transportRole='caption'] { color:#8f99a4; font-size:10px; font-weight:bold; letter-spacing:0.5px; }"
            "QLabel[transportRole='lcd'] { color:#7BE7FF; background:#0B1118; border:1px solid #2A3948; border-radius:3px; padding:3px 8px; font-family:Consolas; font-size:11px; }"
            "QLabel[transportRole='bpm'] { color:#f2cc7f; background:#111820; border:1px solid #3a2f17; border-radius:3px; padding:3px 7px; font-family:Consolas; font-size:10px; font-weight:bold; }"
            "QPushButton[transportRole='toggle'] { background:#1f2a36; border:1px solid #35485f; border-top-color:#496684; border-left-color:#496684; color:#d6e6f5; padding:3px 8px; border-radius:3px; }"
            "QPushButton[transportRole='toggle']:pressed { background:#16222d; border-top-color:#2b3b4c; border-left-color:#2b3b4c; }"
            "QPushButton[transportRole='toggle']:checked { background:#2c3f55; border-color:#67a5d8; color:#ffffff; }"
            "QPushButton#LoopAmberToggle { background:#2a2617; border:1px solid #7d6022; border-top-color:#b08a3a; border-left-color:#b08a3a; color:#f8dea7; }"
            "QPushButton#LoopAmberToggle:checked { background:#584111; border-color:#f0b84f; color:#fff1c8; }"
            "QPushButton[transportRole='nav'] { background:#1b2733; border:1px solid #325070; border-top-color:#4d7aa8; border-left-color:#4d7aa8; color:#d4e7fb; font-weight:bold; border-radius:4px; }"
            "QPushButton[transportRole='nav']:hover { border-color:#74C7FF; color:#ffffff; }"
            "QPushButton[transportRole='nav']:pressed { background:#12202d; border-top-color:#294158; border-left-color:#294158; }"
            "QLineEdit[transportRole='field'] { background:#10151b; border:1px solid #2D3A46; color:#D7DEE6; padding:3px 6px; }"
        )

        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(8, 6, 8, 6)
        shell_layout.setSpacing(10)

        left_cluster = QFrame(shell)
        left_layout = QHBoxLayout(left_cluster)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        left_label = QLabel("INPUT")
        left_label.setProperty("transportRole", "caption")
        left_layout.addWidget(left_label)
        self.mixer_input_combo = QComboBox(left_cluster)
        self.mixer_input_combo.setMinimumWidth(150)
        self.mixer_input_combo.currentIndexChanged.connect(self._on_mixer_input_changed)
        left_layout.addWidget(self.mixer_input_combo)
        self.mixer_monitor_toggle = QPushButton("MON", left_cluster)
        self.mixer_monitor_toggle.setCheckable(True)
        self.mixer_monitor_toggle.setProperty("transportRole", "toggle")
        self.mixer_monitor_toggle.clicked.connect(self._on_mixer_monitor_toggled)
        left_layout.addWidget(self.mixer_monitor_toggle)
        self.mixer_gain_slider = QSlider(Qt.Orientation.Horizontal, left_cluster)
        self.mixer_gain_slider.setRange(0, 100)
        self.mixer_gain_slider.setValue(75)
        self.mixer_gain_slider.setFixedWidth(100)
        self.mixer_gain_slider.valueChanged.connect(self._on_mixer_gain_changed)
        left_layout.addWidget(self.mixer_gain_slider)
        shell_layout.addWidget(left_cluster)

        center_cluster = QFrame(shell)
        center_layout = QVBoxLayout(center_cluster)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(3)
        transport_row = QHBoxLayout()
        transport_row.setContentsMargins(0, 0, 0, 0)
        transport_row.setSpacing(8)

        self.mixer_jump_start_btn = QPushButton("⏮", center_cluster)
        self.mixer_jump_start_btn.setProperty("transportRole", "nav")
        self.mixer_jump_start_btn.setFixedSize(36, 36)
        self.mixer_jump_start_btn.setToolTip("Jump to transport start")
        self.mixer_jump_start_btn.clicked.connect(self._on_mixer_jump_start)
        transport_row.addWidget(self.mixer_jump_start_btn)

        for attr_name in ("record_button", "stop_button", "undo_button", "redo_button", "click_button"):
            button = getattr(transport_bar_widget, attr_name, None)
            if button is not None:
                button.setFixedSize(36, 36)

        transport_row.addWidget(transport_bar_widget)

        self.mixer_jump_end_btn = QPushButton("⏭", center_cluster)
        self.mixer_jump_end_btn.setProperty("transportRole", "nav")
        self.mixer_jump_end_btn.setFixedSize(36, 36)
        self.mixer_jump_end_btn.setToolTip("Jump to transport end")
        self.mixer_jump_end_btn.clicked.connect(self._on_mixer_jump_end)
        transport_row.addWidget(self.mixer_jump_end_btn)

        self.mixer_bars_beats_label = QLabel("1:1:000", center_cluster)
        self.mixer_bars_beats_label.setProperty("transportRole", "lcd")
        transport_row.addWidget(self.mixer_bars_beats_label)
        self.mixer_clock_label = QLabel("00:00:00:000", center_cluster)
        self.mixer_clock_label.setProperty("transportRole", "lcd")
        transport_row.addWidget(self.mixer_clock_label)
        center_layout.addLayout(transport_row)

        self.mixer_seek_slider = QSlider(Qt.Orientation.Horizontal, center_cluster)
        self.mixer_seek_slider.setRange(0, 1000)
        self.mixer_seek_slider.setValue(0)
        self.mixer_seek_slider.valueChanged.connect(self._on_mixer_seek_changed)
        center_layout.addWidget(self.mixer_seek_slider)
        shell_layout.addWidget(center_cluster, stretch=1)

        right_cluster = QFrame(shell)
        right_layout = QHBoxLayout(right_cluster)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)
        self.mixer_loop_toggle = QPushButton("LOOP", right_cluster)
        self.mixer_loop_toggle.setObjectName("LoopAmberToggle")
        self.mixer_loop_toggle.setCheckable(True)
        self.mixer_loop_toggle.setProperty("transportRole", "toggle")
        self.mixer_loop_toggle.clicked.connect(self._on_mixer_loop_toggled)
        right_layout.addWidget(self.mixer_loop_toggle)
        self.mixer_loop_start = QLineEdit(right_cluster)
        self.mixer_loop_start.setProperty("transportRole", "field")
        self.mixer_loop_start.setPlaceholderText("L start")
        self.mixer_loop_start.setFixedWidth(62)
        right_layout.addWidget(self.mixer_loop_start)
        self.mixer_loop_end = QLineEdit(right_cluster)
        self.mixer_loop_end.setProperty("transportRole", "field")
        self.mixer_loop_end.setPlaceholderText("L end")
        self.mixer_loop_end.setFixedWidth(62)
        right_layout.addWidget(self.mixer_loop_end)

        self.mixer_click_toggle = QPushButton("CLICK", right_cluster)
        self.mixer_click_toggle.setCheckable(True)
        self.mixer_click_toggle.setProperty("transportRole", "toggle")
        self.mixer_click_toggle.clicked.connect(self._on_mixer_click_toggled)
        right_layout.addWidget(self.mixer_click_toggle)

        self.mixer_bpm_mirror = QLabel("120 BPM", right_cluster)
        self.mixer_bpm_mirror.setProperty("transportRole", "bpm")
        self.mixer_bpm_mirror.setToolTip("BPM mirror synced from timeline controller")
        right_layout.addWidget(self.mixer_bpm_mirror)

        self.mixer_punch_toggle = QPushButton("PUNCH", right_cluster)
        self.mixer_punch_toggle.setCheckable(True)
        self.mixer_punch_toggle.setProperty("transportRole", "toggle")
        self.mixer_punch_toggle.clicked.connect(self._on_mixer_punch_toggled)
        right_layout.addWidget(self.mixer_punch_toggle)
        self.mixer_punch_in = QLineEdit(right_cluster)
        self.mixer_punch_in.setProperty("transportRole", "field")
        self.mixer_punch_in.setPlaceholderText("P in")
        self.mixer_punch_in.setFixedWidth(56)
        right_layout.addWidget(self.mixer_punch_in)
        self.mixer_punch_out = QLineEdit(right_cluster)
        self.mixer_punch_out.setProperty("transportRole", "field")
        self.mixer_punch_out.setPlaceholderText("P out")
        self.mixer_punch_out.setFixedWidth(56)
        right_layout.addWidget(self.mixer_punch_out)

        apply_btn = QPushButton("Apply", right_cluster)
        apply_btn.clicked.connect(self._apply_mixer_transport_ranges)
        right_layout.addWidget(apply_btn)
        shell_layout.addWidget(right_cluster)

        layout.addWidget(shell)
        self._sync_mixer_transport_controls_from_window()
        self._sync_mixer_transport_readouts(int(self.timeline_controller.get_playhead()) if self.timeline_controller else 0)
        self._sync_mixer_bpm_mirror(float(self.timeline_controller.get_bpm()) if self.timeline_controller else 120.0)

    def _sync_mixer_transport_controls_from_window(self) -> None:
        window = self.window()
        if hasattr(self, "mixer_input_combo"):
            self.mixer_input_combo.blockSignals(True)
            self.mixer_input_combo.clear()
            source_combo = getattr(window, "input_device_combo", None)
            if source_combo is not None:
                for i in range(source_combo.count()):
                    self.mixer_input_combo.addItem(source_combo.itemText(i), source_combo.itemData(i))
                selected_id = source_combo.currentData()
                idx = self.mixer_input_combo.findData(selected_id)
                self.mixer_input_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.mixer_input_combo.blockSignals(False)

        rc = getattr(window, "recording_controller", None)
        if rc is None:
            return

        monitoring_enabled, monitor_gain_percent = rc.get_monitor_state()
        if hasattr(self, "mixer_monitor_toggle"):
            self.mixer_monitor_toggle.blockSignals(True)
            self.mixer_monitor_toggle.setChecked(bool(monitoring_enabled))
            self.mixer_monitor_toggle.blockSignals(False)
        if hasattr(self, "mixer_gain_slider"):
            self.mixer_gain_slider.blockSignals(True)
            self.mixer_gain_slider.setValue(int(monitor_gain_percent))
            self.mixer_gain_slider.blockSignals(False)

        if hasattr(self, "mixer_loop_toggle"):
            self.mixer_loop_toggle.blockSignals(True)
            self.mixer_loop_toggle.setChecked(bool(rc.loop_enabled))
            self.mixer_loop_toggle.blockSignals(False)

            loop_start = rc.samples_to_bars(rc.loop_start_samples)
            self.mixer_loop_start.setText(f"{loop_start:.2f}")
            if rc.loop_end_samples is None:
                self.mixer_loop_end.setText("")
            else:
                loop_end = rc.samples_to_bars(rc.loop_end_samples)
                self.mixer_loop_end.setText(f"{loop_end:.2f}")

        if hasattr(self, "mixer_punch_toggle"):
            self.mixer_punch_toggle.blockSignals(True)
            self.mixer_punch_toggle.setChecked(bool(rc.punch_enabled))
            self.mixer_punch_toggle.blockSignals(False)

            punch_in = rc.samples_to_bars(rc.punch_in_samples)
            self.mixer_punch_in.setText(f"{punch_in:.2f}")
            if rc.punch_out_samples is None:
                self.mixer_punch_out.setText("")
            else:
                punch_out = rc.samples_to_bars(rc.punch_out_samples)
                self.mixer_punch_out.setText(f"{punch_out:.2f}")

        if hasattr(self, "mixer_click_toggle"):
            metronome_running = bool(getattr(getattr(rc, "metronome", None), "is_running", False))
            self.mixer_click_toggle.blockSignals(True)
            self.mixer_click_toggle.setChecked(metronome_running)
            self.mixer_click_toggle.blockSignals(False)

    def _on_mixer_input_changed(self, _index: int) -> None:
        window = self.window()
        source_combo = getattr(window, "input_device_combo", None)
        if source_combo is None or not hasattr(self, "mixer_input_combo"):
            return
        selected_id = self.mixer_input_combo.currentData()
        idx = source_combo.findData(selected_id)
        if idx >= 0:
            source_combo.setCurrentIndex(idx)

    def _on_mixer_monitor_toggled(self, enabled: bool) -> None:
        window = self.window()
        rc = getattr(window, "recording_controller", None)
        if rc is not None:
            rc.set_monitoring_enabled(bool(enabled))
        if hasattr(window, "update_status"):
            window.update_status(f"Mixer monitor {'enabled' if enabled else 'disabled'}")

    def _on_mixer_gain_changed(self, value: int) -> None:
        window = self.window()
        rc = getattr(window, "recording_controller", None)
        if rc is not None:
            rc.set_monitor_gain_percent(int(value))
        if hasattr(window, "update_status"):
            window.update_status(f"Mixer monitor gain set to {int(value)}%")

    def _on_mixer_seek_changed(self, value: int) -> None:
        if self._syncing_mixer_seek_slider:
            return
        window = self.window()
        set_playhead = getattr(window, "_set_project_playhead_ms", None)
        if not callable(set_playhead):
            return
        project = getattr(window, "current_project", None)
        if project is None:
            return
        duration_fn = getattr(window, "_current_transport_target_range", None)
        if callable(duration_fn):
            _start_ms, end_ms, _source = duration_fn()
            max_ms = max(1, int(end_ms))
        else:
            max_ms = 1
        target_ms = int(round((max_ms * int(value)) / 1000.0))
        set_playhead(target_ms)

    def _sync_mixer_transport_readouts(self, playhead_ms: int) -> None:
        if not hasattr(self, "mixer_bars_beats_label"):
            return
        bars_text, time_text = self._format_mixer_transport_time(int(playhead_ms))
        self.mixer_bars_beats_label.setText(bars_text)
        self.mixer_clock_label.setText(time_text)

        if hasattr(self, "mixer_seek_slider"):
            window = self.window()
            duration_fn = getattr(window, "_current_transport_target_range", None)
            if callable(duration_fn):
                _start_ms, end_ms, _source = duration_fn()
                max_ms = max(1, int(end_ms))
                slider_value = max(0, min(1000, int(round((int(playhead_ms) / max_ms) * 1000.0))))
                self._syncing_mixer_seek_slider = True
                try:
                    self.mixer_seek_slider.setValue(slider_value)
                finally:
                    self._syncing_mixer_seek_slider = False

    def _sync_mixer_bpm_mirror(self, bpm: float) -> None:
        if hasattr(self, "mixer_bpm_mirror"):
            self.mixer_bpm_mirror.setText(f"{int(round(float(bpm)))} BPM")

    def _format_mixer_transport_time(self, playhead_ms: int) -> tuple[str, str]:
        bpm = float(self.timeline_controller.get_bpm()) if self.timeline_controller is not None else 120.0
        time_sig = str(self.timeline_controller.get_time_signature()) if self.timeline_controller is not None else "4/4"
        try:
            beats_per_bar = max(1, int(time_sig.split("/", 1)[0]))
        except Exception:
            beats_per_bar = 4

        total_seconds = max(0.0, float(playhead_ms) / 1000.0)
        total_beats = total_seconds * (max(1.0, bpm) / 60.0)
        full_beats = int(total_beats)
        bar_number = (full_beats // beats_per_bar) + 1
        beat_number = (full_beats % beats_per_bar) + 1
        ticks = int(round((total_beats - float(full_beats)) * 960.0))
        bars_text = f"{bar_number}:{beat_number}:{ticks:03d}"

        total_ms = max(0, int(playhead_ms))
        hours = total_ms // 3600000
        minutes = (total_ms // 60000) % 60
        seconds = (total_ms // 1000) % 60
        millis = total_ms % 1000
        time_text = f"{hours:02d}:{minutes:02d}:{seconds:02d}:{millis:03d}"
        return bars_text, time_text

    def _on_mixer_click_toggled(self, _enabled: bool) -> None:
        window = self.window()
        toggle = getattr(window, "toggle_metronome", None)
        if callable(toggle):
            toggle()
            self._sync_mixer_transport_controls_from_window()

    def _on_mixer_jump_start(self) -> None:
        window = self.window()
        callback = getattr(window, "jump_to_transport_start", None)
        if callable(callback):
            callback()

    def _on_mixer_jump_end(self) -> None:
        window = self.window()
        callback = getattr(window, "jump_to_transport_end", None)
        if callable(callback):
            callback()

    def _on_mixer_loop_toggled(self, enabled: bool) -> None:
        window = self.window()
        rc = getattr(window, "recording_controller", None)
        if rc is None:
            return
        rc.set_loop_enabled(bool(enabled))
        if hasattr(window, "update_recording_status_label"):
            window.update_recording_status_label()

    def _on_mixer_punch_toggled(self, enabled: bool) -> None:
        window = self.window()
        rc = getattr(window, "recording_controller", None)
        if rc is None:
            return
        rc.set_punch_enabled(bool(enabled))
        if hasattr(window, "update_recording_status_label"):
            window.update_recording_status_label()

    def _apply_mixer_transport_ranges(self) -> None:
        window = self.window()
        rc = getattr(window, "recording_controller", None)
        if rc is None:
            return

        loop_start_text = self.mixer_loop_start.text().strip() if hasattr(self, "mixer_loop_start") else ""
        loop_end_text = self.mixer_loop_end.text().strip() if hasattr(self, "mixer_loop_end") else ""
        if loop_end_text:
            try:
                loop_start = float(loop_start_text) if loop_start_text else 0.0
                loop_end = float(loop_end_text)
                if not rc.set_loop_range_bars(loop_start, loop_end):
                    raise ValueError(rc.status.last_error or "Invalid loop range")
            except Exception as exc:
                QMessageBox.warning(self, "Loop Range", str(exc))

        punch_in_text = self.mixer_punch_in.text().strip() if hasattr(self, "mixer_punch_in") else ""
        punch_out_text = self.mixer_punch_out.text().strip() if hasattr(self, "mixer_punch_out") else ""
        try:
            punch_in = float(punch_in_text) if punch_in_text else 0.0
            punch_out = float(punch_out_text) if punch_out_text else None
            if not rc.set_punch_range_bars(punch_in, punch_out):
                raise ValueError(rc.status.last_error or "Invalid punch range")
        except Exception as exc:
            QMessageBox.warning(self, "Punch Range", str(exc))

        self._sync_mixer_transport_controls_from_window()
        if hasattr(window, "update_recording_status_label"):
            window.update_recording_status_label()

    def get_timeline_widget_container(self) -> QWidget:
        """Return the waveform area container for inserting TimelineWidget."""
        return self.waveform_area if hasattr(self, "waveform_area") else self

    def get_master_section_container(self) -> QWidget:
        """Return the master section container for setup."""
        return self.master_section if hasattr(self, "master_section") else self

    def get_sidebar_container(self) -> QWidget:
        """Return the sidebar container for setup."""
        return self.sidebar_panel if hasattr(self, "sidebar_panel") else self
