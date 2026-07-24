import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
    QStatusBar, QPushButton, QFileDialog, QHBoxLayout, QLineEdit,
    QMessageBox, QDialog, QTextEdit, QListWidget, QListWidgetItem,
    QTabWidget, QScrollArea, QSlider, QDial, QGroupBox, QGridLayout,
    QFrame, QSizePolicy, QProgressBar, QSpinBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from project_model import Project, Track, Clip, new_empty_project, save_project, load_project
from audio_info import get_audio_length_ms
from timeline_widget import TimelineWidget
from playback_mixer import play_project
from stems_engine import separate_stems, add_stems_to_project

from app_paths import ECHO_ROOT, PROJECTS_DIR, VOICES_DIR, ensure_dirs
from first_run import is_first_run, mark_first_run_done

from voice_store import load_voice_profiles, add_voice_profile
from voice_recorder import record_voice_to_wav
from voice_interface import VoiceProfileConfig
from voice_effects import apply_voice_conversion

from music_generator import generate_music_clip
from song_planner import generate_song_sections
from recording_controller import RecordingController
from recording_ui_components import TrackMeterWidget, TransportBar

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
    padding: 8px 20px;
    margin-right: 2px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    font-weight: 600;
    font-size: 12px;
}
QTabBar::tab:selected {
    background: #e94560;
    color: #ffffff;
}
QTabBar::tab:hover:!selected {
    background: #1a4080;
    color: #ffffff;
}
QPushButton {
    background-color: #0f3460;
    color: #dde1e7;
    border: 1px solid #1a4080;
    padding: 5px 14px;
    border-radius: 4px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #1a4080;
    border-color: #e94560;
}
QPushButton:pressed {
    background-color: #e94560;
    color: #ffffff;
}
QPushButton:disabled {
    background-color: #0a1930;
    color: #444;
    border-color: #222;
}
QPushButton#SoloButton {
    background-color: #1c2e1c;
    color: #888;
    border: 2px solid #2a4a2a;
    border-radius: 13px;
    font-weight: bold;
    font-size: 11px;
}
QPushButton#SoloButton:checked {
    background-color: #f0c040;
    color: #111;
    border-color: #ffd700;
}
QPushButton#SoloButton:hover:!checked {
    background-color: #2a4a2a;
    color: #ccc;
}
QPushButton#MuteButton {
    background-color: #2e1c1c;
    color: #888;
    border: 2px solid #4a2a2a;
    border-radius: 13px;
    font-weight: bold;
    font-size: 11px;
}
QPushButton#MuteButton:checked {
    background-color: #e94560;
    color: #fff;
    border-color: #ff6080;
}
QPushButton#MuteButton:hover:!checked {
    background-color: #4a2a2a;
    color: #ccc;
}
QSlider::groove:horizontal {
    height: 5px;
    background: #0a1930;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -5px 0;
    background: #e94560;
    border-radius: 7px;
    border: 2px solid #ffd0d8;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0f3460, stop:1 #e94560);
    border-radius: 3px;
}
QDial {
    background: #0f3460;
}
QLineEdit {
    background-color: #0d1b2a;
    color: #dde1e7;
    border: 1px solid #0f3460;
    padding: 4px 8px;
    border-radius: 4px;
    selection-background-color: #e94560;
}
QLineEdit:focus {
    border-color: #e94560;
}
QTextEdit {
    background-color: #0d1b2a;
    color: #dde1e7;
    border: 1px solid #0f3460;
    border-radius: 4px;
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
    font-size: 11px;
}
QFrame#TrackMixerRow {
    background-color: #1e2a3a;
    border: 1px solid #1a3050;
    border-radius: 6px;
}
QFrame#TrackMixerRow:hover {
    border-color: #e94560;
}
QProgressBar {
    background-color: #0a1930;
    border: 1px solid #0f3460;
    border-radius: 3px;
    text-align: center;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #00c853, stop:0.65 #ffd600, stop:1 #e94560);
    border-radius: 2px;
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: #0d1b2a; width: 8px; border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #0f3460; border-radius: 4px; min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QStatusBar {
    background-color: #0a1020;
    color: #aab4be;
    font-size: 10px;
    border-top: 1px solid #0f3460;
}
QListWidget {
    background-color: #0d1b2a;
    border: 1px solid #0f3460;
    border-radius: 4px;
    color: #dde1e7;
}
QListWidget::item:selected { background-color: #e94560; color: #fff; }
QListWidget::item:hover { background-color: #1a4080; }
"""


class LevelMeterBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(0)
        self.setTextVisible(False)
        self.setFixedHeight(7)
        self.setOrientation(Qt.Horizontal)

    def set_db(self, db_value: float) -> None:
        normalized = max(0.0, min(1.0, (db_value + 60.0) / 60.0))
        self.setValue(int(normalized * 100))


class TrackMixerRow(QFrame):
    def __init__(self, track_index: int, track_name: str, on_volume_change=None, parent=None):
        super().__init__(parent)
        self.track_index = track_index
        self._on_volume_change = on_volume_change

        self.setObjectName("TrackMixerRow")
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedHeight(76)

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(10)

        badge = QLabel(str(track_index + 1))
        badge.setFixedSize(22, 22)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            "background:#0f3460; border-radius:11px; color:#e94560;"
            "font-weight:bold; font-size:10px;"
        )
        root.addWidget(badge)

        self.name_label = QLabel(track_name)
        self.name_label.setMinimumWidth(90)
        self.name_label.setMaximumWidth(130)
        self.name_label.setStyleSheet("font-weight:500; color:#dde1e7;")
        self.name_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        root.addWidget(self.name_label)

        self.solo_btn = QPushButton("S")
        self.solo_btn.setCheckable(True)
        self.solo_btn.setFixedSize(26, 26)
        self.solo_btn.setObjectName("SoloButton")
        self.solo_btn.setToolTip("Solo this track")
        root.addWidget(self.solo_btn)

        self.mute_btn = QPushButton("M")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setFixedSize(26, 26)
        self.mute_btn.setObjectName("MuteButton")
        self.mute_btn.setToolTip("Mute this track")
        root.addWidget(self.mute_btn)

        vol_col = QVBoxLayout()
        vol_col.setSpacing(2)
        vol_col.setContentsMargins(0, 0, 0, 0)

        vol_top = QHBoxLayout()
        vol_top.setContentsMargins(0, 0, 0, 0)
        vol_icon = QLabel("VOL")
        vol_icon.setStyleSheet("font-size:9px; color:#555; font-weight:bold; letter-spacing:1px;")
        self.db_label = QLabel("0 dB")
        self.db_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.db_label.setMinimumWidth(52)
        self.db_label.setStyleSheet("font-size:10px; color:#e94560; font-weight:bold;")
        vol_top.addWidget(vol_icon)
        vol_top.addStretch()
        vol_top.addWidget(self.db_label)
        vol_col.addLayout(vol_top)

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(-60, 6)
        self.vol_slider.setValue(0)
        self.vol_slider.setToolTip("Track volume (dB)")
        self.vol_slider.valueChanged.connect(self._volume_changed)
        vol_col.addWidget(self.vol_slider)

        root.addLayout(vol_col, stretch=1)

        pan_col = QVBoxLayout()
        pan_col.setSpacing(1)
        pan_col.setAlignment(Qt.AlignCenter)
        self.pan_knob = QDial()
        self.pan_knob.setRange(-100, 100)
        self.pan_knob.setValue(0)
        self.pan_knob.setFixedSize(36, 36)
        self.pan_knob.setNotchesVisible(True)
        self.pan_knob.setObjectName("PanKnob")
        self.pan_knob.setToolTip("Pan left / right")
        pan_lbl = QLabel("PAN")
        pan_lbl.setAlignment(Qt.AlignCenter)
        pan_lbl.setStyleSheet("font-size:8px; color:#444; letter-spacing:1px;")
        pan_col.addWidget(self.pan_knob, alignment=Qt.AlignCenter)
        pan_col.addWidget(pan_lbl)
        root.addLayout(pan_col)

        meter_col = QVBoxLayout()
        meter_col.setSpacing(1)
        self.level_meter = LevelMeterBar()
        self.level_meter.setMinimumWidth(80)
        self.peak_label = QLabel("-inf")
        self.peak_label.setAlignment(Qt.AlignCenter)
        self.peak_label.setStyleSheet("font-size:8px; color:#666;")
        meter_col.addWidget(self.level_meter)
        meter_col.addWidget(self.peak_label)
        root.addLayout(meter_col)

    def _volume_changed(self, value: int):
        self.db_label.setText(f"{value:+d} dB" if value != 0 else "0 dB")
        if self._on_volume_change:
            self._on_volume_change(self.track_index, float(value))

    def set_volume_db(self, db: float):
        self.vol_slider.blockSignals(True)
        self.vol_slider.setValue(int(db))
        v = int(db)
        self.db_label.setText(f"{v:+d} dB" if v != 0 else "0 dB")
        self.vol_slider.blockSignals(False)

    def update_meter(self, current_db: float, peak_db: float):
        self.level_meter.set_db(current_db)
        self.peak_label.setText(f"{peak_db:.0f}")

    @property
    def is_muted(self) -> bool:
        return self.mute_btn.isChecked()

    @property
    def is_soloed(self) -> bool:
        return self.solo_btn.isChecked()


class FirstRunDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Welcome to Echo Pro")
        self.setMinimumWidth(420)
        layout = QVBoxLayout()
        text = QTextEdit()
        text.setReadOnly(True)
        text.setText(
            "Welcome to Echo Pro!\n\n"
            "This app lets you:\n"
            "- Create and save multitrack projects\n"
            "- Split songs into stems\n"
            "- Record and manage your own voice profiles\n"
            "- Generate music clips (placeholder for now)\n\n"
            "Projects will be stored in:\n"
            f"{PROJECTS_DIR}\n\n"
            "Click 'Close' to start using Echo Pro."
        )
        layout.addWidget(text)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        self.setLayout(layout)


class ProjectBrowserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Project from Library")
        self.setMinimumWidth(500)
        layout = QVBoxLayout()
        self.list_box = QTextEdit()
        self.list_box.setReadOnly(True)
        projects = [str(f) for f in PROJECTS_DIR.glob("*.eproj")]
        if projects:
            self.list_box.setText("\n".join(projects))
        else:
            self.list_box.setText("No projects found in:\n" + str(PROJECTS_DIR))
        layout.addWidget(self.list_box)
        self.selected_path = None
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Paste or type full path to project")
        layout.addWidget(self.path_input)
        open_btn = QPushButton("Open this project")
        open_btn.clicked.connect(self.choose_project)
        layout.addWidget(open_btn)
        self.setLayout(layout)

    def choose_project(self):
        text = self.path_input.text().strip()
        if text:
            self.selected_path = text
            self.accept()


class VoiceManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Voice Manager")
        self.setMinimumWidth(500)
        layout = QVBoxLayout()
        layout.addWidget(QLabel(
            "Voice profiles are recordings of voices you own or have permission to use.\n"
            "Do not use other people's voices without their consent."
        ))
        self.voice_list = QListWidget()
        self.refresh_voice_list()
        layout.addWidget(self.voice_list)
        name_layout = QHBoxLayout()
        self.new_voice_name = QLineEdit()
        self.new_voice_name.setPlaceholderText("New voice profile name")
        name_layout.addWidget(self.new_voice_name)
        record_btn = QPushButton("Record New Voice (10s)")
        record_btn.clicked.connect(self.record_new_voice)
        name_layout.addWidget(record_btn)
        layout.addLayout(name_layout)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        self.setLayout(layout)

    def refresh_voice_list(self):
        self.voice_list.clear()
        for p in load_voice_profiles():
            item = QListWidgetItem(f"{p.name} [{p.file_path}]")
            item.setData(Qt.UserRole, p)
            self.voice_list.addItem(item)

    def record_new_voice(self):
        name = self.new_voice_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Input error", "Please enter a name for the voice profile.")
            return
        confirm = QMessageBox.question(
            self, "Consent confirmation",
            "You should only record your own voice or voices you have explicit permission to use.\n\n"
            "Do you confirm this?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return
        output_wav = VOICES_DIR / f"{name.replace(' ', '_')}.wav"
        try:
            record_voice_to_wav(output_wav, duration_sec=10)
            add_voice_profile(name, output_wav)
            self.new_voice_name.clear()
            self.refresh_voice_list()
            QMessageBox.information(self, "Voice recorded", f"Saved voice profile: {name}")
        except Exception as e:
            QMessageBox.critical(self, "Recording error", f"Failed to record voice:\n{e}")


class EchoProWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Echo Pro")

        self.current_project: Project = new_empty_project("Untitled")
        self.next_clip_id = 1
        self.recording_controller = RecordingController("default_session", self.current_project.name)
        self.recording_meters: dict = {}
        self.mixer_rows: list = []

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.recording_timer = QTimer(self)
        self.recording_timer.setInterval(100)
        self.recording_timer.timeout.connect(self.refresh_recording_meters)
        self.recording_timer.start()

        root = QVBoxLayout()
        root.setContentsMargins(8, 8, 8, 4)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.project_name_label = QLabel("Echo Pro  -  Untitled")
        self.project_name_label.setStyleSheet(
            "font-size:16px; font-weight:bold; color:#e94560; padding:2px 6px;"
        )
        header.addWidget(self.project_name_label)
        header.addStretch()
        for label, slot in [
            ("New", self.new_project),
            ("Open", self.open_project),
            ("Save", self.save_project_dialog),
            ("Browse", self.browse_projects),
        ]:
            btn = QPushButton(label)
            btn.setFixedWidth(70)
            btn.clicked.connect(slot)
            header.addWidget(btn)
        root.addLayout(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #0f3460;")
        root.addWidget(sep)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_mixer_tab(), "  Mixer  ")
        self.tabs.addTab(self._build_recording_tab(), "  Recording  ")
        self.tabs.addTab(self._build_generate_tab(), "  Generate  ")
        self.tabs.addTab(self._build_voice_tab(), "  Voice FX  ")
        root.addWidget(self.tabs, stretch=1)

        timeline_group = QGroupBox("Timeline")
        tl_layout = QVBoxLayout(timeline_group)
        tl_layout.setContentsMargins(4, 4, 4, 4)
        self.timeline = TimelineWidget(self.current_project)
        tl_layout.addWidget(self.timeline)
        root.addWidget(timeline_group)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)
        self.update_status("Ready")

    def _build_mixer_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        controls_group = QGroupBox("Track Controls")
        ctrl_layout = QHBoxLayout(controls_group)
        ctrl_layout.setSpacing(8)

        self.new_track_name = QLineEdit()
        self.new_track_name.setPlaceholderText("New track name...")
        self.new_track_name.setFixedWidth(160)
        ctrl_layout.addWidget(self.new_track_name)

        add_track_btn = QPushButton("+ Track")
        add_track_btn.clicked.connect(self.add_track)
        ctrl_layout.addWidget(add_track_btn)

        ctrl_layout.addWidget(self._vsep())

        self.clip_track_index_input = QLineEdit()
        self.clip_track_index_input.setPlaceholderText("Track #")
        self.clip_track_index_input.setFixedWidth(60)
        ctrl_layout.addWidget(self.clip_track_index_input)

        self.clip_start_sec_input = QLineEdit()
        self.clip_start_sec_input.setPlaceholderText("Start (s)")
        self.clip_start_sec_input.setFixedWidth(70)
        ctrl_layout.addWidget(self.clip_start_sec_input)

        add_clip_btn = QPushButton("+ Clip")
        add_clip_btn.clicked.connect(self.add_clip_from_file)
        ctrl_layout.addWidget(add_clip_btn)

        ctrl_layout.addWidget(self._vsep())

        stems_btn = QPushButton("Split Stems")
        stems_btn.clicked.connect(self.split_song_into_stems)
        ctrl_layout.addWidget(stems_btn)

        play_btn = QPushButton("Play")
        play_btn.setStyleSheet(
            "QPushButton { background:#0f5430; border-color:#00c853; }"
            "QPushButton:hover { background:#00a844; }"
            "QPushButton:pressed { background:#00c853; color:#000; }"
        )
        play_btn.clicked.connect(self.play_current_project)
        ctrl_layout.addWidget(play_btn)

        ctrl_layout.addStretch()

        ctrl_layout.addWidget(QLabel("Cloud:"))
        self.cloud_enabled = QLineEdit()
        self.cloud_enabled.setPlaceholderText("yes/no")
        self.cloud_enabled.setFixedWidth(60)
        ctrl_layout.addWidget(self.cloud_enabled)

        layout.addWidget(controls_group)

        mixer_group = QGroupBox("Tracks")
        mixer_outer = QVBoxLayout(mixer_group)
        mixer_outer.setContentsMargins(4, 4, 4, 4)

        self.mixer_scroll = QScrollArea()
        self.mixer_scroll.setWidgetResizable(True)
        self.mixer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.mixer_inner = QWidget()
        self.mixer_layout = QVBoxLayout(self.mixer_inner)
        self.mixer_layout.setContentsMargins(4, 4, 4, 4)
        self.mixer_layout.setSpacing(4)
        self.mixer_layout.addStretch()

        self.mixer_scroll.setWidget(self.mixer_inner)
        mixer_outer.addWidget(self.mixer_scroll)
        layout.addWidget(mixer_group, stretch=1)

        self._rebuild_mixer_rows()
        return tab

    def _build_recording_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        transport_group = QGroupBox("Transport")
        tg_layout = QHBoxLayout(transport_group)
        tg_layout.setSpacing(10)

        self.transport_bar = TransportBar()
        self.transport_bar.record_button.clicked.connect(self.start_recording_session)
        self.transport_bar.stop_button.clicked.connect(self.stop_recording_session)
        self.transport_bar.undo_button.clicked.connect(self.undo_last_recording_take)
        self.transport_bar.redo_button.clicked.connect(self.redo_last_recording_take)
        self.transport_bar.click_button.clicked.connect(self.toggle_metronome)
        self.transport_bar.stop_button.setEnabled(False)
        tg_layout.addWidget(self.transport_bar)

        tg_layout.addWidget(self._vsep())

        self.record_track_input = QLineEdit()
        self.record_track_input.setPlaceholderText("Track #")
        self.record_track_input.setFixedWidth(60)
        tg_layout.addWidget(self.record_track_input)

        arm_btn = QPushButton("Arm Track")
        arm_btn.clicked.connect(self.arm_recording_track)
        tg_layout.addWidget(arm_btn)

        arm_all_btn = QPushButton("Arm All")
        arm_all_btn.clicked.connect(self.arm_all_recording_tracks)
        tg_layout.addWidget(arm_all_btn)

        clear_armed_btn = QPushButton("Clear Armed")
        clear_armed_btn.clicked.connect(self.clear_armed_recording_tracks)
        tg_layout.addWidget(clear_armed_btn)

        tg_layout.addWidget(self._vsep())

        tg_layout.addWidget(QLabel("BPM:"))
        self.record_tempo_input = QLineEdit()
        self.record_tempo_input.setPlaceholderText("120")
        self.record_tempo_input.setFixedWidth(55)
        tg_layout.addWidget(self.record_tempo_input)

        set_tempo_btn = QPushButton("Set Tempo")
        set_tempo_btn.clicked.connect(self.set_recording_tempo)
        tg_layout.addWidget(set_tempo_btn)

        tg_layout.addStretch()
        layout.addWidget(transport_group)

        self.recording_status_label = QLabel("Recording: idle")
        self.recording_status_label.setStyleSheet(
            "font-size:11px; color:#aab4be; padding:4px 8px;"
            "background:#0d1b2a; border-radius:4px; border:1px solid #0f3460;"
        )
        layout.addWidget(self.recording_status_label)

        meters_group = QGroupBox("Input Levels")
        meters_outer = QVBoxLayout(meters_group)
        meters_outer.setContentsMargins(4, 4, 4, 4)

        meter_scroll = QScrollArea()
        meter_scroll.setWidgetResizable(True)
        meter_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.meter_inner = QWidget()
        self.meter_container = QVBoxLayout(self.meter_inner)
        self.meter_container.setContentsMargins(4, 4, 4, 4)
        self.meter_container.setSpacing(3)
        self.meter_container.addStretch()

        meter_scroll.setWidget(self.meter_inner)
        meters_outer.addWidget(meter_scroll)
        layout.addWidget(meters_group, stretch=1)

        self._build_recording_meters()
        return tab

    def _build_generate_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        gen_group = QGroupBox("Music Generator - Single Clip")
        gen_grid = QGridLayout(gen_group)
        gen_grid.setSpacing(8)

        gen_grid.addWidget(QLabel("Style:"), 0, 0)
        self.gen_style = QLineEdit()
        self.gen_style.setPlaceholderText("lofi, rock...")
        gen_grid.addWidget(self.gen_style, 0, 1)

        gen_grid.addWidget(QLabel("Genre:"), 0, 2)
        self.gen_genre = QLineEdit()
        self.gen_genre.setPlaceholderText("EDM, orchestral...")
        gen_grid.addWidget(self.gen_genre, 0, 3)

        gen_grid.addWidget(QLabel("Mood:"), 1, 0)
        self.gen_mood = QLineEdit()
        self.gen_mood.setPlaceholderText("calm, energetic...")
        gen_grid.addWidget(self.gen_mood, 1, 1)

        gen_grid.addWidget(QLabel("Lyrics:"), 1, 2)
        self.gen_lyrics = QLineEdit()
        self.gen_lyrics.setPlaceholderText("Lyrics snippet")
        gen_grid.addWidget(self.gen_lyrics, 1, 3)

        gen_grid.addWidget(QLabel("Duration (s):"), 2, 0)
        self.gen_duration = QLineEdit()
        self.gen_duration.setPlaceholderText("10-30")
        self.gen_duration.setFixedWidth(60)
        gen_grid.addWidget(self.gen_duration, 2, 1)

        gen_btn = QPushButton("Generate Clip")
        gen_btn.setStyleSheet(
            "QPushButton { background:#1a0f40; border-color:#7040e0; }"
            "QPushButton:hover { background:#3020a0; }"
        )
        gen_btn.clicked.connect(self.generate_single_clip)
        gen_grid.addWidget(gen_btn, 2, 3)

        layout.addWidget(gen_group)

        plan_group = QGroupBox("Song Planner - Full Song")
        plan_grid = QGridLayout(plan_group)
        plan_grid.setSpacing(8)

        plan_grid.addWidget(QLabel("Total length (s):"), 0, 0)
        self.plan_total_length = QLineEdit()
        self.plan_total_length.setPlaceholderText("180")
        plan_grid.addWidget(self.plan_total_length, 0, 1)

        plan_grid.addWidget(QLabel("Structure:"), 0, 2)
        self.plan_structure = QLineEdit()
        self.plan_structure.setPlaceholderText("Intro,Verse,Chorus,Outro")
        plan_grid.addWidget(self.plan_structure, 0, 3)

        plan_grid.addWidget(QLabel("Key:"), 1, 0)
        self.plan_key = QLineEdit()
        self.plan_key.setPlaceholderText("C major")
        plan_grid.addWidget(self.plan_key, 1, 1)

        plan_grid.addWidget(QLabel("Chords:"), 1, 2)
        self.plan_chords = QLineEdit()
        self.plan_chords.setPlaceholderText("C-G-Am-F")
        plan_grid.addWidget(self.plan_chords, 1, 3)

        plan_grid.addWidget(QLabel("Time sig:"), 2, 0)
        self.plan_time_sig = QLineEdit()
        self.plan_time_sig.setPlaceholderText("4/4")
        plan_grid.addWidget(self.plan_time_sig, 2, 1)

        plan_grid.addWidget(QLabel("Tempo (BPM):"), 2, 2)
        self.plan_tempo = QLineEdit()
        self.plan_tempo.setPlaceholderText("120")
        plan_grid.addWidget(self.plan_tempo, 2, 3)

        plan_grid.addWidget(QLabel("Lyrics:"), 3, 0)
        self.plan_lyrics = QTextEdit()
        self.plan_lyrics.setPlaceholderText("Full lyrics...")
        self.plan_lyrics.setFixedHeight(80)
        plan_grid.addWidget(self.plan_lyrics, 3, 1, 1, 3)

        plan_btn = QPushButton("Generate Full Song")
        plan_btn.setStyleSheet(
            "QPushButton { background:#1a0f40; border-color:#7040e0; }"
            "QPushButton:hover { background:#3020a0; }"
        )
        plan_btn.clicked.connect(self.generate_full_song)
        plan_grid.addWidget(plan_btn, 4, 3)

        layout.addWidget(plan_group)
        layout.addStretch()
        return tab

    def _build_voice_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        effect_group = QGroupBox("Apply Voice Effect to Clip")
        eg_grid = QGridLayout(effect_group)
        eg_grid.setSpacing(8)

        eg_grid.addWidget(QLabel("Track #:"), 0, 0)
        self.voice_track_index_input = QLineEdit()
        self.voice_track_index_input.setPlaceholderText("0, 1, 2...")
        self.voice_track_index_input.setFixedWidth(60)
        eg_grid.addWidget(self.voice_track_index_input, 0, 1)

        eg_grid.addWidget(QLabel("Clip ID:"), 0, 2)
        self.voice_clip_id_input = QLineEdit()
        self.voice_clip_id_input.setPlaceholderText("Clip ID")
        self.voice_clip_id_input.setFixedWidth(60)
        eg_grid.addWidget(self.voice_clip_id_input, 0, 3)

        eg_grid.addWidget(QLabel("Voice profile:"), 1, 0)
        self.voice_profile_name_input = QLineEdit()
        self.voice_profile_name_input.setPlaceholderText("Profile name")
        eg_grid.addWidget(self.voice_profile_name_input, 1, 1, 1, 3)

        btn_row = QHBoxLayout()
        apply_voice_btn = QPushButton("Apply Voice Effect")
        apply_voice_btn.clicked.connect(self.apply_voice_effect_to_clip)
        btn_row.addWidget(apply_voice_btn)
        manage_voices_btn = QPushButton("Manage Voices")
        manage_voices_btn.clicked.connect(self.open_voice_manager)
        btn_row.addWidget(manage_voices_btn)
        btn_row.addStretch()
        eg_grid.addLayout(btn_row, 2, 0, 1, 4)

        layout.addWidget(effect_group)
        layout.addStretch()
        return tab

    def _vsep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color:#1a4080;")
        sep.setFixedWidth(2)
        return sep

    def _rebuild_mixer_rows(self):
        while self.mixer_layout.count() > 1:
            item = self.mixer_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.mixer_rows = []
        for i, track in enumerate(self.current_project.tracks):
            row = TrackMixerRow(
                track_index=i,
                track_name=track.name,
                on_volume_change=self._on_track_volume_changed,
            )
            row.set_volume_db(track.volume_db)
            self.mixer_layout.insertWidget(self.mixer_layout.count() - 1, row)
            self.mixer_rows.append(row)

    def _on_track_volume_changed(self, track_index: int, db: float):
        if 0 <= track_index < len(self.current_project.tracks):
            self.current_project.tracks[track_index].volume_db = db
            self.update_status(f"Track {track_index + 1} volume: {db:+.0f} dB")

    def _build_recording_meters(self):
        while self.meter_container.count() > 1:
            item = self.meter_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.recording_meters = {}
        for track in self.recording_controller.engine.tracks:
            meter = TrackMeterWidget(f"Track {track.track_id + 1}")
            self.meter_container.insertWidget(self.meter_container.count() - 1, meter)
            self.recording_meters[track.track_id] = meter

    def update_recording_status_label(self):
        s = self.recording_controller.get_status_snapshot()
        state = "recording" if s.is_recording else "armed" if s.is_armed else "idle"
        armed = ", ".join(str(t) for t in s.active_track_ids) or "none"
        self.recording_status_label.setText(
            f"Recording: {state}  |  Tempo: {s.current_tempo_bpm} BPM  |  "
            f"Time Sig: {s.time_signature}  |  Armed: {armed}"
        )

    def refresh_recording_meters(self):
        levels = self.recording_controller.get_meter_levels()
        for track_id, meter in self.recording_meters.items():
            lv = levels.get(track_id)
            if lv is not None:
                meter.update_levels(lv["current_db"], lv["peak_db"])
        for track_id, lv in levels.items():
            if track_id < len(self.mixer_rows):
                self.mixer_rows[track_id].update_meter(lv["current_db"], lv["peak_db"])
        self.update_recording_status_label()

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
            QMessageBox.warning(self, "Input error",
                                self.recording_controller.status.last_error or "Could not arm track.")

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

    def toggle_metronome(self):
        if self.recording_controller.metronome.is_running:
            self.recording_controller.metronome.stop()
            self.transport_bar.click_button.setText("Metronome On")
            self.update_status("Metronome stopped")
        else:
            self.recording_controller.metronome.start()
            self.transport_bar.click_button.setText("Metronome Off")
            self.update_status("Metronome started")
        self.update_recording_status_label()

    def start_recording_session(self):
        if not self.recording_controller.armed_tracks:
            QMessageBox.warning(self, "Recording", "Arm at least one track before recording.")
            return
        self.recording_controller.session.project_name = self.current_project.name
        if not self.recording_controller.start_stream():
            QMessageBox.critical(self, "Recording error",
                                 self.recording_controller.status.last_error or "Could not start audio stream.")
            return
        if not self.recording_controller.start_recording():
            QMessageBox.critical(self, "Recording error",
                                 self.recording_controller.status.last_error or "Could not start recording.")
            self.recording_controller.stop_stream()
            return
        self.transport_bar.record_button.setEnabled(False)
        self.transport_bar.stop_button.setEnabled(True)
        self.update_status("Recording started")
        self.update_recording_status_label()

    def stop_recording_session(self):
        if self.recording_controller.status.is_recording:
            self.recording_controller.stop_recording(duration_seconds=0.0, level_stats={})
            self.recording_controller.stop_stream()
        self.transport_bar.record_button.setEnabled(True)
        self.transport_bar.stop_button.setEnabled(False)
        self.transport_bar.click_button.setText("Metronome On")
        self.update_status("Recording stopped")
        self.update_recording_status_label()

    def undo_last_recording_take(self):
        take = self.recording_controller.undo_last_take()
        self.update_status("Nothing to undo" if take is None else
                           f"Undid take {take.take_number} on track {take.track_id}")
        self.update_recording_status_label()

    def redo_last_recording_take(self):
        take = self.recording_controller.redo_last_take()
        self.update_status("Nothing to redo" if take is None else
                           f"Redid take {take.take_number} on track {take.track_id}")
        self.update_recording_status_label()

    def update_status(self, text: str):
        self.status.showMessage(text)

    def refresh_timeline(self):
        self.timeline.set_project(self.current_project)
        self.timeline.update()

    def new_project(self):
        self.current_project = new_empty_project("Untitled")
        self.project_name_label.setText("Echo Pro  -  Untitled")
        self.next_clip_id = 1
        self.recording_controller = RecordingController("new_session", self.current_project.name)
        self._build_recording_meters()
        self._rebuild_mixer_rows()
        self.update_recording_status_label()
        self.refresh_timeline()
        self.update_status("New project created")

    def open_project(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Echo Pro Project", "", "Echo Projects (*.eproj);;All Files (*)"
        )
        if not filename:
            return
        try:
            proj = load_project(Path(filename))
            self._apply_loaded_project(proj, filename)
            self.update_status(f"Opened project: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")

    def _apply_loaded_project(self, proj: Project, source_label: str):
        self.current_project = proj
        self.project_name_label.setText(f"Echo Pro  -  {proj.name}")
        max_id = max((c.id for c in proj.clips), default=0)
        self.next_clip_id = max_id + 1
        self.recording_controller = RecordingController(
            f"session_{proj.name.replace(' ', '_')}", proj.name
        )
        self._build_recording_meters()
        self._rebuild_mixer_rows()
        self.update_recording_status_label()
        self.refresh_timeline()

    def save_project_dialog(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Echo Pro Project", "", "Echo Projects (*.eproj)"
        )
        if not filename:
            return
        if not filename.lower().endswith(".eproj"):
            filename += ".eproj"
        try:
            path = Path(filename)
            self.current_project.name = path.stem
            save_project(self.current_project, path)
            self.project_name_label.setText(f"Echo Pro  -  {self.current_project.name}")
            self.update_status(f"Saved project: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{e}")

    def browse_projects(self):
        dlg = ProjectBrowserDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.selected_path:
            try:
                proj = load_project(Path(dlg.selected_path))
                self._apply_loaded_project(proj, dlg.selected_path)
                self.update_status(f"Opened from library: {dlg.selected_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")

    def add_track(self):
        name = self.new_track_name.text().strip() or f"Track {len(self.current_project.tracks) + 1}"
        self.current_project.tracks.append(Track(name=name))
        self.recording_controller.session.ensure_track(len(self.current_project.tracks) - 1)
        self.new_track_name.clear()
        self._build_recording_meters()
        self._rebuild_mixer_rows()
        self.refresh_timeline()
        self.update_status(f"Added track: {name}")

    def add_clip_from_file(self):
        try:
            track_index = int(self.clip_track_index_input.text())
        except ValueError:
            QMessageBox.warning(self, "Input error", "Track index must be a number.")
            return
        if not (0 <= track_index < len(self.current_project.tracks)):
            QMessageBox.warning(self, "Input error", "Track index out of range.")
            return
        try:
            start_sec = float(self.clip_start_sec_input.text())
        except ValueError:
            start_sec = 0.0
        filename, _ = QFileDialog.getOpenFileName(
            self, "Choose audio file", "", "Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)"
        )
        if not filename:
            return
        try:
            length_ms = get_audio_length_ms(filename)
            clip = Clip(
                id=self.next_clip_id, track_index=track_index,
                file_path=filename, start_ms=int(start_sec * 1000), length_ms=length_ms
            )
            self.current_project.clips.append(clip)
            self.next_clip_id += 1
            self.refresh_timeline()
            self.update_status(f"Added clip on track {track_index} from {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add clip:\n{e}")

    def set_track_volume(self):
        pass

    def play_current_project(self):
        self.update_status("Mixing and playing project...")
        QApplication.processEvents()
        try:
            play_project(self.current_project)
            self.update_status("Playback finished")
        except Exception as e:
            QMessageBox.critical(self, "Playback error", f"Could not play project:\n{e}")
            self.update_status("Playback error")

    def split_song_into_stems(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Choose song to split into stems", "",
            "Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)"
        )
        if not filename:
            return
        try:
            song_path = Path(filename)
            stems_root = song_path.parent / "echo_stems"
            song_stems_dir = stems_root / song_path.stem
            self.update_status("Running Demucs... this may take a while.")
            QApplication.processEvents()
            stems = separate_stems(str(song_path), song_stems_dir)
            self.next_clip_id = add_stems_to_project(
                self.current_project, stems, song_stems_dir,
                next_clip_id_start=self.next_clip_id
            )
            self._rebuild_mixer_rows()
            self.refresh_timeline()
            self.update_status("Stems added to project.")
            QMessageBox.information(self, "Stems created",
                                    "Stems were created and added as tracks.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to split stems:\n{e}")
            self.update_status("Stems error")

    def open_voice_manager(self):
        dlg = VoiceManagerDialog(self)
        dlg.exec()
        self.update_status("Voice manager closed")

    def apply_voice_effect_to_clip(self):
        try:
            track_index = int(self.voice_track_index_input.text())
        except ValueError:
            QMessageBox.warning(self, "Input error", "Track index must be a number.")
            return
        try:
            clip_id = int(self.voice_clip_id_input.text())
        except ValueError:
            QMessageBox.warning(self, "Input error", "Clip ID must be a number.")
            return
        profile_name = self.voice_profile_name_input.text().strip()
        if not profile_name:
            QMessageBox.warning(self, "Input error", "Please enter a voice profile name.")
            return
        target_clip = next(
            (c for c in self.current_project.clips
             if c.id == clip_id and c.track_index == track_index), None
        )
        if target_clip is None:
            QMessageBox.warning(self, "Not found", "No clip found with that ID and track index.")
            return
        profiles = load_voice_profiles()
        selected_profile = next((p for p in profiles if p.name == profile_name), None)
        if selected_profile is None:
            QMessageBox.warning(self, "Not found", "No voice profile with that name.")
            return
        if not selected_profile.consent_flag:
            QMessageBox.warning(self, "Consent required",
                                "This voice profile is not marked as consented.")
            return
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
                source_wav=source_path, target_profile=vp_config,
                output_path=output_path, preserve_pitch=True,
                preserve_formants=True, strength=1.0,
                notes=f"Applied via Echo Pro to clip {clip_id}"
            )
            new_track_index = len(self.current_project.tracks)
            new_track_name = f"{profile_name} (converted)"
            self.current_project.tracks.append(Track(name=new_track_name))
            length_ms = get_audio_length_ms(str(result.audio_path))
            new_clip = Clip(
                id=self.next_clip_id, track_index=new_track_index,
                file_path=str(result.audio_path),
                start_ms=target_clip.start_ms, length_ms=length_ms
            )
            self.current_project.clips.append(new_clip)
            self.next_clip_id += 1
            self._rebuild_mixer_rows()
            self.refresh_timeline()
            self.update_status(f"Voice conversion applied, new track: {new_track_name}")
            QMessageBox.information(self, "Voice conversion applied",
                                    "A placeholder voice conversion was applied.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to apply voice conversion:\n{e}")
            self.update_status("Voice conversion error")

    def generate_single_clip(self):
        try:
            style = self.gen_style.text()
            genre = self.gen_genre.text()
            mood = self.gen_mood.text()
            lyrics = self.gen_lyrics.text()
            duration_sec = int(self.gen_duration.text())
            use_cloud = self.cloud_enabled.text().strip().lower() == "yes"
            project_id = self.current_project.name.replace(" ", "_") or "default_project"
            result = generate_music_clip(
                style=style, genre=genre, mood=mood, lyrics=lyrics,
                duration_seconds=duration_sec, key="", chords="",
                time_signature="4/4", tempo_bpm=120,
                section_name=f"clip_{self.next_clip_id}", seed=None,
                project_id=project_id, use_cloud=use_cloud
            )
            length_ms = get_audio_length_ms(str(result.audio_path))
            new_track_index = len(self.current_project.tracks)
            self.current_project.tracks.append(Track(name=f"Generated {self.next_clip_id}"))
            self.current_project.clips.append(Clip(
                id=self.next_clip_id, track_index=new_track_index,
                file_path=str(result.audio_path), start_ms=0, length_ms=length_ms
            ))
            self.next_clip_id += 1
            self._rebuild_mixer_rows()
            self.refresh_timeline()
            self.update_status("Generated clip added to project.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate clip:\n{e}")

    def generate_full_song(self):
        try:
            total_length_sec = int(self.plan_total_length.text())
            structure = [s.strip() for s in self.plan_structure.text().split(",") if s.strip()]
            key = self.plan_key.text()
            chords = self.plan_chords.text()
            time_sig = self.plan_time_sig.text()
            tempo = int(self.plan_tempo.text())
            lyrics = self.plan_lyrics.toPlainText()
            use_cloud = self.cloud_enabled.text().strip().lower() == "yes"
            project_id = self.current_project.name.replace(" ", "_") or "default_project"
            clip_paths = generate_song_sections(
                lyrics=lyrics, structure=structure,
                total_length_sec=total_length_sec, key=key, chords=chords,
                time_signature=time_sig, tempo=tempo,
                style="", genre="", mood="",
                project_id=project_id, use_cloud=use_cloud
            )
            for path in clip_paths:
                length_ms = get_audio_length_ms(str(path))
                new_track_index = len(self.current_project.tracks)
                self.current_project.tracks.append(Track(name=f"Section {new_track_index}"))
                self.current_project.clips.append(Clip(
                    id=self.next_clip_id, track_index=new_track_index,
                    file_path=str(path), start_ms=0, length_ms=length_ms
                ))
                self.next_clip_id += 1
            self._rebuild_mixer_rows()
            self.refresh_timeline()
            self.update_status("Full song generated (placeholder clips).")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate full song:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLE)

    ensure_dirs()

    if is_first_run():
        dlg = FirstRunDialog()
        dlg.exec()
        mark_first_run_done()

    win = EchoProWindow()
    win.resize(1280, 820)
    win.show()
    sys.exit(app.exec())