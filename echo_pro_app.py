
# pyright: reportAttributeAccessIssue=false, reportArgumentType=false

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple


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
    QComboBox, QProgressDialog,
    QMessageBox, QDialog, QTextEdit, QListWidget, QListWidgetItem,
    QTabWidget, QScrollArea, QGroupBox, QGridLayout,
    QFrame, QSizePolicy, QSplitter, QMenu
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPen

from project_model import Clip, Project, Track, TrackPlaybackSettings, new_empty_project, save_project, load_project
from audio_info import get_audio_length_ms
from timeline_widget import TimelineWidget
from playback_mixer import is_playback_active, play_project, project_duration_ms, stop_playback
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

from app_paths import ECHO_ROOT, PROJECTS_DIR, VOICES_DIR, ensure_dirs
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
from tools.dev.p5a_regression_runner import format_regression_summary, run_phase5a_regression_checks
from tools.dev.p5b_regression_runner import format_regression_summary as format_p5b_regression_summary, run_phase5b_regression_checks
from recording_recovery import RecoverySnapshotManager
from input_validation import parse_float, parse_int, parse_time_signature, run_common_validation_checks

from app.styles import DARK_STYLE
from app.ui.dialogs.first_run_dialog import FirstRunDialog
from app.ui.dialogs.project_browser_dialog import ProjectBrowserDialog
from app.ui.dialogs.track_playback_settings_dialog import TrackPlaybackSettingsDialog
from app.ui.dialogs.voice_manager_dialog import VoiceManagerDialog
from app.ui.widgets.collapsible_panel import CollapsiblePanel
from app.ui.widgets.title_bar import CustomTitleBar
from app.ui.widgets.track_mixer_row import TrackMixerRow
from app.ui.widgets.main_mixer_layout import MainMixerLayout

# Symbolic stereo waveform placeholder shown in the Master Output section.
_MASTER_WAVEFORM_PLACEHOLDER = (
    "\u25ac\u25ac\u2580\u2584\u2580\u2588\u2580\u2584\u2580\u25ac  MASTER L  \u25ac\u25ac\u25ac  "
    "MASTER R  \u25ac\u2580\u2584\u2580\u2588\u2580\u2584\u2580\u25ac\u25ac"
)


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
        self.stem_source_path: Optional[Path] = None
        self.stem_output_dir: Optional[Path] = None
        self._stem_activity_lines: list[str] = []

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
        if hasattr(self, "transport_bar") and hasattr(self.transport_bar, "set_metronome_enabled"):
            self.transport_bar.set_metronome_enabled(running)

    def _on_timeline_project_changed(self):
        self.refresh_timeline()
        self.update_status("Timeline updated")

    def refresh_alter_section_selector(self):
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
        value = self.alter_section_selector.currentData()
        if value is not None:
            self.alter_section_index_input.setText(str(value))

    def _append_stem_activity(self, text: str, *, reset: bool = False) -> None:
        if not hasattr(self, "stem_activity_view"):
            return
        message = text.strip()
        if reset:
            self._stem_activity_lines = []
        if not message:
            self.stem_activity_view.setPlainText("\n".join(self._stem_activity_lines))
            return
        if self._stem_activity_lines and self._stem_activity_lines[-1] == message:
            return
        self._stem_activity_lines.append(message)
        self._stem_activity_lines = self._stem_activity_lines[-10:]
        self.stem_activity_view.setPlainText("\n".join(self._stem_activity_lines))

    def _set_stem_status(self, summary: str, *, detail: Optional[str] = None, reset_activity: bool = False) -> None:
        if hasattr(self, "stem_status_label"):
            self.stem_status_label.setText(summary)
        self._append_stem_activity(detail or summary, reset=reset_activity)

    def _update_stem_backend_summary(self) -> None:
        if not hasattr(self, "stem_backend_label"):
            return
        capability = get_stem_backend_capability()
        backend_text = f"Backend: {capability['backend']}"
        if capability["ready"]:
            backend_text += f" ready ({capability['demucs_executable']})"
        else:
            backend_text += f" needs setup - {capability['reason']}"
        self.stem_backend_label.setText(backend_text)

    def _refresh_stem_section_state(self) -> None:
        self._update_stem_backend_summary()
        if not hasattr(self, "stem_split_btn"):
            return

        selected_source = self.stem_source_path
        source_exists = selected_source is not None and selected_source.exists()
        self.stem_split_btn.setEnabled(bool(source_exists))

        if hasattr(self, "stem_source_input"):
            self.stem_source_input.setText(str(selected_source) if selected_source is not None else "")

        if hasattr(self, "stem_output_label"):
            if selected_source is not None:
                output_dir = selected_source.parent / "echo_stems" / selected_source.stem
                self.stem_output_dir = output_dir
                self.stem_output_label.setText(f"Output folder: {output_dir}")
            else:
                self.stem_output_dir = None
                self.stem_output_label.setText("Output folder: choose source audio to preview the stem folder.")

        if not source_exists and hasattr(self, "stem_status_label"):
            self.stem_status_label.setText("Choose source audio to enable Demucs splitting.")

    def _set_stem_source_path(self, song_path: Optional[Path]) -> None:
        self.stem_source_path = song_path.resolve() if song_path is not None else None
        self._refresh_stem_section_state()
        if self.stem_source_path is not None:
            self._set_stem_status(
                "Stem source ready.",
                detail=f"Selected source audio: {self.stem_source_path.name}",
                reset_activity=True,
            )

    def choose_stem_source_audio(self) -> None:
        initial_dir = ""
        if self.stem_source_path is not None:
            initial_dir = str(self.stem_source_path.parent)
        elif PROJECTS_DIR.exists():
            initial_dir = str(PROJECTS_DIR)
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choose song to split into stems",
            initial_dir,
            "Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)"
        )
        if not filename:
            return
        self._set_stem_source_path(Path(filename))

    def _selected_demucs_model(self) -> str:
        if hasattr(self, "stem_model_combo"):
            model_name = self.stem_model_combo.currentData()
            if isinstance(model_name, str) and model_name.strip():
                return model_name
        return DEFAULT_DEMUCS_MODEL

    def run_selected_stem_split(self) -> None:
        if self.stem_source_path is None or not self.stem_source_path.exists():
            self.choose_stem_source_audio()
            if self.stem_source_path is None or not self.stem_source_path.exists():
                return
        self._split_song_into_stems_for_path(self.stem_source_path)

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
            engine_track = self.recording_controller.engine.get_track(idx)
            if engine_track is None:
                continue
            engine_track.name = project_track.name
            engine_track.set_volume_db(project_track.volume_db)
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
            self.track_list.addItem(f"{idx}: {track.name} ({track.volume_db:.1f} dB){flag_text}")

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
        self.recording_status_label.setText(
            f"Recording: {state} | Tempo: {status.current_tempo_bpm} BPM | Time Sig: {status.time_signature} | Count-In: {count_in_bars} bar(s) | Roll(pre/post): {roll_text} | Punch: {punch_text} | Loop: {loop_text} | Armed: {armed_text}"
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
            self.transport_bar.record_button.setEnabled(True)
            self.transport_bar.stop_button.setEnabled(False)
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
        self.update_status("Audio device list refreshed")

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

    def run_p5a_regression_checks(self):
        self.update_status("Running P5A regression checks...")
        report = run_phase5a_regression_checks()
        summary = format_regression_summary(report)

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
            QMessageBox.information(self, "P5A Regression Checks", summary)
        else:
            QMessageBox.warning(self, "P5A Regression Checks", summary)

        self.update_status(f"P5A regression checks complete: {passed_count} passed, {failed_count} failed")

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

    def on_loop_mode_changed(self, *_args):
        enabled = bool(self.loop_mode_combo.currentData())
        if enabled and bool(self.punch_mode_combo.currentData()):
            self.punch_mode_combo.setCurrentIndex(self.punch_mode_combo.findData(False))
            self.recording_controller.set_punch_enabled(False)
            self.update_status("Punch mode disabled because loop mode was enabled")
        self.recording_controller.set_loop_enabled(enabled)
        self.update_status("Loop mode enabled" if enabled else "Loop mode disabled")
        self.update_recording_status_label()

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

        self.transport_bar.record_button.setEnabled(False)
        self.transport_bar.stop_button.setEnabled(True)
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

        self.transport_bar.record_button.setEnabled(True)
        self.transport_bar.stop_button.setEnabled(False)
        self._sync_metronome_button_state(False)
        self.refresh_take_review_list()
        self.update_status("Recording stopped")
        self.update_recording_status_label()

    def undo_last_recording_take(self):
        take = self.recording_controller.undo_last_take()
        if take is None:
            self.update_status("Nothing to undo")
        else:
            self._sync_take_clips_for_track(int(take.track_id))
            self.refresh_timeline()
            self.update_status(f"Undid take {take.take_number} on track {take.track_id}")
        self.refresh_take_review_list()
        self.update_recording_status_label()

    def redo_last_recording_take(self):
        take = self.recording_controller.redo_last_take()
        if take is None:
            self.update_status("Nothing to redo")
        else:
            self._sync_take_clips_for_track(int(take.track_id))
            self.refresh_timeline()
            self.update_status(f"Redid take {take.take_number} on track {take.track_id}")
        self.refresh_take_review_list()
        self.update_recording_status_label()

    def update_status(self, text: str):
        self.status.showMessage(text)

    def _update_playback_position_label(self) -> None:
        self.playback_position_label.setText(f"Playhead {self.project_playhead_ms / 1000.0:.2f}s")

    def _set_project_playhead_ms(self, value_ms: int) -> None:
        project_end_ms = project_duration_ms(self.current_project)
        self.project_playhead_ms = max(0, min(int(value_ms), project_end_ms))
        self.timeline.set_playhead_ms(self.project_playhead_ms)
        self._update_playback_position_label()

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
        self._set_project_playhead_ms(int(start_ms))
        self.update_status(f"Moved playhead to {source} start at {start_ms / 1000.0:.2f}s")

    def jump_to_transport_end(self) -> None:
        _start_ms, end_ms, source = self._current_transport_target_range()
        self._set_project_playhead_ms(int(end_ms))
        self.update_status(f"Moved playhead to {source} end at {end_ms / 1000.0:.2f}s")

    def _update_project_playback_controls(self, is_playing: bool) -> None:
        self.play_project_btn.setEnabled(not is_playing)
        self.stop_project_btn.setEnabled(is_playing)

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
        self._update_project_playback_controls(False)

    def _poll_project_playback(self) -> None:
        if self._project_playback_started_at is None:
            self.project_playback_timer.stop()
            self._update_project_playback_controls(False)
            return

        elapsed_ms = int(max(0.0, (time.monotonic() - self._project_playback_started_at) * 1000.0))
        current_ms = min(self._project_playback_end_ms, self._project_playback_start_ms + elapsed_ms)
        self._set_project_playhead_ms(current_ms)

        if not is_playback_active():
            self._finish_project_playback(stopped_manually=self._project_playback_manual_stop)

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
        self.timeline.updateGeometry()
        self.timeline.update()

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

    def new_project(self):
        if self._project_playback_started_at is not None or is_playback_active():
            self.stop_current_project_playback()
        self.current_project = new_empty_project("Untitled")
        self.project_name_label.setText("Project: Untitled")
        self.next_clip_id = 1
        self.last_song_generation = None
        self.project_playhead_ms = 0
        self._persist_song_generation_metadata()
        self.recording_controller = RecordingController("new_session", self.current_project.name)
        self.recording_controller.restore_session_preferences()
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
        self.update_status("New project created")

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
            self.update_status(f"Opened project: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")

    def save_project_dialog(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Echo Pro Project",
            "",
            "Echo Projects (*.eproj)"
        )
        if not filename:
            return
        if not filename.lower().endswith(".eproj"):
            filename += ".eproj"
        try:
            path = Path(filename)
            self.current_project.name = path.stem
            save_project(self.current_project, path)
            self.project_name_label.setText(f"Project: {self.current_project.name}")
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
                self.refresh_timeline()
                self.update_status(f"Opened project from library: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")

    def add_track(self):
        name = self.track_name_input.text().strip()
        if not name:
            name = f"Track {len(self.current_project.tracks)}"
        self.current_project.tracks.append(Track(name=name))
        self.recording_controller.session.ensure_track(len(self.current_project.tracks) - 1)
        self.selected_track_index = len(self.current_project.tracks) - 1
        self.track_name_input.clear()
        self.sync_project_tracks_to_recording_engine()
        self._build_recording_meters()
        self.refresh_track_list()
        self.refresh_timeline()
        self.update_status(f"Added track: {name}")

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
            self._project_playback_start_ms = start_ms
            self._project_playback_end_ms = start_ms + int(played_duration_ms)
            self._project_playback_manual_stop = False
            self._project_playback_started_at = time.monotonic()
            self._update_project_playback_controls(True)
            self.project_playback_timer.start()
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
        self.run_selected_stem_split()

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

    def generate_single_clip(self):
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
                    seed=None,
                    project_id=project_id,
                    use_cloud=use_cloud
                )
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
            self.update_status(f"Generated clip added to project (backend: {capability['backend']}).")
            if not capability["ready"]:
                QMessageBox.information(
                    self,
                    "Music backend status",
                    f"{capability['reason']}\n\nGenerated clip uses the current installed local backend until all optional assets are available.",
                )
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


class TabbedEchoProWindow(EchoProWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.setWindowTitle("Echo Pro")
        self.setMinimumSize(1100, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(DARK_STYLE)

        self._initialize_shared_window_state()
        self.mixer_rows = []

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self._initialize_shared_window_timers(start_recording_timer=False)

        self._build_ui()
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
        self.update_status("Ready")

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Custom title bar spans the full window width with no outer margins.
        self._title_bar = CustomTitleBar(self)
        root.addWidget(self._title_bar)

        # Wrap all existing content in a padded widget below the title bar.
        _content = QWidget()
        _content_layout = QVBoxLayout(_content)
        _content_layout.setContentsMargins(10, 6, 10, 8)
        _content_layout.setSpacing(8)

        header = QHBoxLayout()
        self.project_name_label = QLabel("Project: Untitled")
        self.project_name_label.setStyleSheet("font-size:13px; font-weight:bold; color:#E2E2E5;")
        header.addWidget(self.project_name_label)
        header.addStretch()

        for symbol, slot, tip in [
            ("+", self.new_project, "Create new project"),
            ("\U0001f4c2", self.open_project, "Open project"),
            ("\U0001f4be", self.save_project_dialog, "Save project"),
            ("\U0001f50d", self.browse_projects, "Browse projects"),
        ]:
            button = QPushButton(symbol)
            self._configure_symbol_button(button, symbol, tip, width=34)
            button.clicked.connect(slot)
            header.addWidget(button)

        _content_layout.addLayout(header)

        self.tabs = QTabWidget()
        # Add Mixer tab as the first/primary tab (item 1.4 - main DAW layout)
        self.mixer_layout = MainMixerLayout()
        self.tabs.addTab(self.mixer_layout, "Mixer")
        self.tabs.addTab(self._wrap_scroll(self._build_overview_tab()), "Home")
        self.tabs.addTab(self._wrap_scroll(self._build_recording_tab()), "Recording")
        self.tabs.addTab(self._wrap_scroll(self._build_voice_tab()), "Voice FX")
        self.tabs.addTab(self._wrap_scroll(self._build_music_tab()), "Music")
        self.tabs.addTab(self._wrap_scroll(self._build_tools_tab()), "Tools")
        self.tabs.addTab(self._build_help_tab(), "Help")
        _content_layout.addWidget(self.tabs, stretch=1)

        root.addWidget(_content, stretch=1)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

    def _wrap_scroll(self, content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(content)
        return scroll

    def _build_overview_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Master stereo waveform display ───────────────────────────────────
        master_content = QWidget()
        master_layout = QVBoxLayout(master_content)
        master_layout.setContentsMargins(4, 4, 4, 4)
        master_wave_frame = QFrame()
        master_wave_frame.setFrameShape(QFrame.StyledPanel)
        master_wave_frame.setFixedHeight(46)
        master_wave_frame.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #0a1020, stop:0.48 #102848, stop:0.52 #102848, stop:1 #0a1020);"
            " border:1px solid #1a4080; border-radius:4px; }"
        )
        master_wave_lbl = QLabel(_MASTER_WAVEFORM_PLACEHOLDER)
        master_wave_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        master_wave_lbl.setStyleSheet("color:#22ee44; font-family: monospace; font-size:11px; letter-spacing:2px;")
        master_wave_lbl.setToolTip("Master stereo waveform display (live view available after playback)")
        master_layout_inner = QVBoxLayout(master_wave_frame)
        master_layout_inner.addWidget(master_wave_lbl)
        master_layout.addWidget(master_wave_frame)
        layout.addWidget(CollapsiblePanel("Master Stereo Output", master_content))

        project_content = QWidget()
        project_layout = QHBoxLayout(project_content)
        project_layout.setSpacing(6)
        project_layout.setContentsMargins(4, 4, 4, 4)
        self.track_name_input = QLineEdit()
        self.track_name_input.setPlaceholderText("Track name")
        self.track_name_input.setFixedWidth(180)
        self.track_name_input.setToolTip("Enter a name for the new or selected track")
        project_layout.addWidget(self.track_name_input)
        for symbol, slot, tip in [
            ("+", self.add_track, "Add track"),
            ("\u270e", self.rename_selected_track, "Rename selected track"),
            ("\u2715", self.delete_selected_track, "Delete selected track"),
            ("\u2191", lambda: self.move_selected_track(-1), "Move selected track up"),
            ("\u2193", lambda: self.move_selected_track(1), "Move selected track down"),
            ("\U0001f507", self.toggle_selected_track_mute, "Toggle mute on selected track"),
            ("\u25ce", self.toggle_selected_track_solo, "Toggle solo on selected track"),
            ("\u23fa", self.toggle_arm_selected_track, "Arm or disarm selected track for recording"),
        ]:
            button = QPushButton(symbol)
            self._configure_symbol_button(button, symbol, tip, width=34)
            button.clicked.connect(slot)
            project_layout.addWidget(button)
        project_layout.addStretch()
        layout.addWidget(CollapsiblePanel("Project Actions", project_content))

        clip_content = QWidget()
        clip_layout = QGridLayout(clip_content)
        clip_layout.setSpacing(8)
        clip_layout.setContentsMargins(4, 4, 4, 4)
        self.clip_track_index_input = QLineEdit()
        self.clip_track_index_input.setPlaceholderText("Track index")
        self.clip_track_index_input.setFixedWidth(90)
        self.clip_track_index_input.setToolTip("Zero-based index of the track to add the clip to")
        clip_layout.addWidget(QLabel("Clip Track"), 0, 0)
        clip_layout.addWidget(self.clip_track_index_input, 0, 1)
        self.clip_start_sec_input = QLineEdit()
        self.clip_start_sec_input.setPlaceholderText("Start sec")
        self.clip_start_sec_input.setFixedWidth(90)
        self.clip_start_sec_input.setToolTip("Start position of the clip in seconds")
        clip_layout.addWidget(QLabel("Start"), 0, 2)
        clip_layout.addWidget(self.clip_start_sec_input, 0, 3)
        add_clip_btn = QPushButton("Add Clip from File")
        add_clip_btn.setToolTip("Browse for an audio file and add it as a clip")
        add_clip_btn.clicked.connect(self.add_clip_from_file)
        self._configure_symbol_button(add_clip_btn, "\U0001f4c2", "Add clip from file")
        clip_layout.addWidget(add_clip_btn, 0, 4)

        self.volume_track_index_input = QLineEdit()
        self.volume_track_index_input.setPlaceholderText("Track index")
        self.volume_track_index_input.setFixedWidth(90)
        self.volume_track_index_input.setToolTip("Zero-based index of the track to adjust volume for")
        clip_layout.addWidget(QLabel("Volume Track"), 1, 0)
        clip_layout.addWidget(self.volume_track_index_input, 1, 1)
        self.volume_db_input = QLineEdit()
        self.volume_db_input.setPlaceholderText("dB")
        self.volume_db_input.setFixedWidth(90)
        self.volume_db_input.setToolTip("Volume level in decibels (e.g. -6, 0, +3)")
        clip_layout.addWidget(QLabel("Volume dB"), 1, 2)
        clip_layout.addWidget(self.volume_db_input, 1, 3)
        set_vol_btn = QPushButton("Set Track Volume")
        set_vol_btn.setToolTip("Apply the specified volume to the selected track")
        set_vol_btn.clicked.connect(self.set_track_volume)
        self._configure_symbol_button(set_vol_btn, "\U0001f50a", "Set track volume")
        clip_layout.addWidget(set_vol_btn, 1, 4)

        self.play_project_btn = QPushButton("Play")
        self.play_project_btn.setToolTip("Play back all tracks in the current project from the current playhead")
        self.play_project_btn.clicked.connect(self.play_current_project)
        self.stop_project_btn = QPushButton("Stop")
        self.stop_project_btn.setToolTip("Stop project playback")
        self.stop_project_btn.clicked.connect(self.stop_current_project_playback)
        self.stop_project_btn.setEnabled(False)
        self.jump_to_transport_start_btn = QPushButton("Jump to Start")
        self.jump_to_transport_start_btn.setToolTip("Jump to the start of the current selection, selected clip, or project")
        self.jump_to_transport_start_btn.clicked.connect(self.jump_to_transport_start)
        self.jump_to_transport_end_btn = QPushButton("Jump to End")
        self.jump_to_transport_end_btn.setToolTip("Jump to the end of the current selection, selected clip, or project")
        self.jump_to_transport_end_btn.clicked.connect(self.jump_to_transport_end)
        self.playback_position_label = QLabel("Playhead 0.00s")
        self.playback_position_label.setToolTip("Current project playhead position")
        self._configure_symbol_button(self.play_project_btn, "\u25b6", "Play project")
        self._configure_symbol_button(self.stop_project_btn, "\u25a0", "Stop playback")
        self._configure_symbol_button(self.jump_to_transport_start_btn, "\u23ee", "Jump to start")
        self._configure_symbol_button(self.jump_to_transport_end_btn, "\u23ed", "Jump to end")
        clip_layout.addWidget(self.play_project_btn, 2, 1)
        clip_layout.addWidget(self.stop_project_btn, 2, 2)
        clip_layout.addWidget(self.jump_to_transport_start_btn, 2, 3)
        clip_layout.addWidget(self.jump_to_transport_end_btn, 2, 4)
        clip_layout.addWidget(self.playback_position_label, 2, 5)
        layout.addWidget(CollapsiblePanel("Audio and Track Tools", clip_content))

        stems_content = QWidget()
        stems_layout = QGridLayout(stems_content)
        stems_layout.setSpacing(8)
        stems_layout.setContentsMargins(4, 4, 4, 4)

        self.stem_backend_label = QLabel()
        self.stem_backend_label.setWordWrap(True)
        stems_layout.addWidget(self.stem_backend_label, 0, 0, 1, 4)

        stems_layout.addWidget(QLabel("Source Audio"), 1, 0)
        self.stem_source_input = QLineEdit()
        self.stem_source_input.setPlaceholderText("Choose a mix to split with Demucs")
        self.stem_source_input.setReadOnly(True)
        self.stem_source_input.setMinimumWidth(320)
        self.stem_source_input.setToolTip("Selected mix that Demucs will separate into stems")
        stems_layout.addWidget(self.stem_source_input, 1, 1, 1, 2)

        choose_stem_source_btn = QPushButton("Choose Source Audio")
        choose_stem_source_btn.setToolTip("Browse for the song or mix that should be split into stems")
        choose_stem_source_btn.clicked.connect(self.choose_stem_source_audio)
        stems_layout.addWidget(choose_stem_source_btn, 1, 3)

        stems_layout.addWidget(QLabel("Demucs Model"), 2, 0)
        self.stem_model_combo = QComboBox()
        self.stem_model_combo.setToolTip("Choose the Demucs model preset used for the split")
        for model_name, model_label in DEMUCS_MODEL_OPTIONS:
            self.stem_model_combo.addItem(f"{model_name} - {model_label}", model_name)
        default_model_index = self.stem_model_combo.findData(DEFAULT_DEMUCS_MODEL)
        if default_model_index >= 0:
            self.stem_model_combo.setCurrentIndex(default_model_index)
        stems_layout.addWidget(self.stem_model_combo, 2, 1)

        self.stem_output_label = QLabel("Output folder: choose source audio to preview the stem folder.")
        self.stem_output_label.setWordWrap(True)
        stems_layout.addWidget(self.stem_output_label, 2, 2, 1, 2)

        self.stem_split_btn = QPushButton("Run Demucs Split")
        self.stem_split_btn.setToolTip("Start splitting the selected source audio into stems")
        self.stem_split_btn.clicked.connect(self.run_selected_stem_split)
        stems_layout.addWidget(self.stem_split_btn, 3, 0)

        self.stem_status_label = QLabel("Choose source audio to enable Demucs splitting.")
        self.stem_status_label.setWordWrap(True)
        stems_layout.addWidget(self.stem_status_label, 3, 1, 1, 3)

        self.stem_activity_view = QTextEdit()
        self.stem_activity_view.setReadOnly(True)
        self.stem_activity_view.setMaximumHeight(110)
        self.stem_activity_view.setToolTip("Recent Demucs activity, progress, and completion messages")
        stems_layout.addWidget(self.stem_activity_view, 4, 0, 1, 4)

        self._refresh_stem_section_state()
        self._append_stem_activity("Stem splitting is idle.", reset=True)
        layout.addWidget(CollapsiblePanel("Stem Splitting (Demucs)", stems_content))

        tracks_content = QWidget()
        tracks_layout = QVBoxLayout(tracks_content)
        tracks_layout.setContentsMargins(4, 4, 4, 4)
        self.track_list = QListWidget()
        self.track_list.setMaximumHeight(120)
        self.track_list.setToolTip("List of all tracks in the project — click to select")
        self.track_list.currentRowChanged.connect(self.on_track_selection_changed)
        tracks_layout.addWidget(self.track_list)
        layout.addWidget(CollapsiblePanel("Tracks", tracks_content))

        # ── Waveforms + Mixer in a resizable splitter ─────────────────────────
        wave_content = QWidget()
        wave_layout = QVBoxLayout(wave_content)
        wave_layout.setContentsMargins(4, 4, 4, 4)
        self.timeline = TimelineWidget(self.current_project)
        self.timeline.setMinimumHeight(360)
        self.timeline.on_project_changed = self._on_timeline_project_changed
        self.timeline.on_comp_range_selected = self.on_timeline_comp_range_selected
        self.timeline.on_add_clip_at = self._on_timeline_add_clip_at
        self.timeline_scroll = QScrollArea()
        self.timeline_scroll.setWidgetResizable(False)
        self.timeline_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.timeline_scroll.setMinimumHeight(380)
        self.timeline_scroll.setWidget(self.timeline)
        wave_hint = QLabel("Right-click on the timeline to add a clip at any position. "
                           "Click a clip to select it; Del/Backspace to delete.")
        wave_hint.setStyleSheet("color:#aab4be; font-style:italic; font-size:10px;")
        wave_layout.addWidget(wave_hint)
        wave_layout.addWidget(self.timeline_scroll)
        wave_panel = CollapsiblePanel("Waveforms", wave_content)

        # ── Studio Mixer – horizontal channel strips ─────────────────────────
        mixer_content = QWidget()
        mixer_layout_outer = QVBoxLayout(mixer_content)
        mixer_layout_outer.setContentsMargins(4, 4, 4, 4)
        mixer_header = QLabel("Vertical channel strips — scroll horizontally to view all channels")
        mixer_header.setStyleSheet("color:#aab4be; font-style:italic;")
        mixer_layout_outer.addWidget(mixer_header)
        self.mixer_scroll = QScrollArea()
        self.mixer_scroll.setWidgetResizable(True)
        self.mixer_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mixer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.mixer_scroll.setMinimumHeight(400)
        self.mixer_inner = QWidget()
        self.mixer_layout = QHBoxLayout(self.mixer_inner)
        self.mixer_layout.setContentsMargins(4, 4, 4, 4)
        self.mixer_layout.setSpacing(6)
        self.mixer_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.mixer_empty_label = QLabel("Add or load tracks to populate the mixer board.")
        self.mixer_empty_label.setStyleSheet("padding:12px; color:#dde1e7; background:#0d1b2a; border:1px solid #1a4080;")
        self.mixer_layout.addWidget(self.mixer_empty_label)
        self.mixer_layout.addStretch()
        self.mixer_scroll.setWidget(self.mixer_inner)
        mixer_layout_outer.addWidget(self.mixer_scroll)
        mixer_panel = CollapsiblePanel("Studio Mixer", mixer_content)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(wave_panel)
        splitter.addWidget(mixer_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([420, 520])
        layout.addWidget(splitter, stretch=1)

        return tab

    def _on_timeline_add_clip_at(self, track_index: int, start_ms: int) -> None:
        """Handle a request from the timeline to add a clip at a given position."""
        if track_index < 0 or track_index >= len(self.current_project.tracks):
            QMessageBox.warning(self, "Add Clip", "No valid track at that position.")
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
            clip = Clip(
                id=self.next_clip_id,
                track_index=track_index,
                file_path=str(file_path),
                start_ms=start_ms,
                length_ms=length_ms,
            )
            self.current_project.clips.append(clip)
            self.next_clip_id += 1
            self.refresh_timeline()
            self.update_status(f"Added clip on track {track_index} at {start_ms / 1000:.2f}s from {file_path.name}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add clip:\n{e}")



    def _build_recording_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        device_group = QGroupBox("Audio Devices and Checks")
        device_layout = QHBoxLayout(device_group)
        self.input_device_combo = QComboBox()
        self.input_device_combo.setToolTip("Select the audio input device for recording")
        self.output_device_combo = QComboBox()
        self.output_device_combo.setToolTip("Select the audio output device for playback")
        device_layout.addWidget(QLabel("Input"))
        device_layout.addWidget(self.input_device_combo)
        device_layout.addWidget(QLabel("Output"))
        device_layout.addWidget(self.output_device_combo)

        device_layout.addWidget(QLabel("Sample Rate"))
        self.sample_rate_combo = QComboBox()
        for sr_label, sr_value in [("44.1 kHz", 44100), ("48 kHz", 48000), ("88.2 kHz", 88200), ("96 kHz", 96000)]:
            self.sample_rate_combo.addItem(sr_label, sr_value)
        self.sample_rate_combo.setToolTip("Recording sample rate (applies to new sessions)")
        device_layout.addWidget(self.sample_rate_combo)

        for symbol, slot, tip in [
            ("\u21bb", self.refresh_audio_device_selectors, "Refresh audio devices"),
            ("\U0001f50a", self.test_audio_devices, "Test audio devices"),
        ]:
            button = QPushButton(symbol)
            self._configure_symbol_button(button, symbol, tip)
            button.clicked.connect(slot)
            device_layout.addWidget(button)
        device_layout.addStretch()
        layout.addWidget(device_group)

        transport_group = QGroupBox("Transport")
        transport_layout = QHBoxLayout(transport_group)
        self.transport_bar = TransportBar()
        self.transport_bar.record_button.clicked.connect(self.start_recording_session)
        self.transport_bar.stop_button.clicked.connect(self.stop_recording_session)
        self.transport_bar.undo_button.clicked.connect(self.undo_last_recording_take)
        self.transport_bar.redo_button.clicked.connect(self.redo_last_recording_take)
        self.transport_bar.click_button.clicked.connect(self.toggle_metronome)
        self.transport_bar.stop_button.setEnabled(False)
        transport_layout.addWidget(self.transport_bar)
        self.record_track_input = QLineEdit()
        self.record_track_input.setPlaceholderText("Arm track")
        self.record_track_input.setFixedWidth(90)
        self.record_track_input.setToolTip("Track index to arm for recording (0-based)")
        transport_layout.addWidget(self.record_track_input)
        for symbol, slot, tip in [
            ("\u23fa", self.arm_recording_track, "Arm selected recording track"),
            ("\u25c9", self.arm_all_recording_tracks, "Arm all tracks for recording"),
            ("\u2298", self.clear_armed_recording_tracks, "Clear all armed recording tracks"),
        ]:
            button = QPushButton(symbol)
            self._configure_symbol_button(button, symbol, tip)
            button.clicked.connect(slot)
            transport_layout.addWidget(button)
        self.record_tempo_input = QLineEdit()
        self.record_tempo_input.setPlaceholderText("BPM")
        self.record_tempo_input.setFixedWidth(80)
        self.record_tempo_input.setToolTip("Recording tempo in beats per minute")
        transport_layout.addWidget(self.record_tempo_input)
        tempo_btn = QPushButton("\u23f1")
        self._configure_symbol_button(tempo_btn, "\u23f1", "Set recording tempo")
        tempo_btn.clicked.connect(self.set_recording_tempo)
        transport_layout.addWidget(tempo_btn)
        self.record_time_sig_input = QLineEdit()
        self.record_time_sig_input.setPlaceholderText("4/4")
        self.record_time_sig_input.setFixedWidth(70)
        self.record_time_sig_input.setToolTip("Time signature for recording (e.g. 4/4, 3/4, 6/8)")
        transport_layout.addWidget(self.record_time_sig_input)
        time_btn = QPushButton("\u2263")
        self._configure_symbol_button(time_btn, "\u2263", "Set recording time signature")
        time_btn.clicked.connect(self.set_recording_time_signature)
        transport_layout.addWidget(time_btn)
        self.record_count_in_input = QLineEdit()
        self.record_count_in_input.setPlaceholderText("Count-in")
        self.record_count_in_input.setFixedWidth(80)
        self.record_count_in_input.setToolTip("Number of count-in bars before recording starts")
        transport_layout.addWidget(self.record_count_in_input)
        count_btn = QPushButton("\u231b")
        self._configure_symbol_button(count_btn, "\u231b", "Set recording count-in")
        count_btn.clicked.connect(self.set_recording_count_in)
        transport_layout.addWidget(count_btn)
        layout.addWidget(transport_group)

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
        layout.addWidget(self.punch_loop_widget)

        status_group = QGroupBox("Recording Status")
        status_layout = QVBoxLayout(status_group)
        self.recording_status_label = QLabel("Recording: idle")
        status_layout.addWidget(self.recording_status_label)
        self.recording_diagnostics_widget = RecordingDiagnosticsWidget()
        status_layout.addWidget(self.recording_diagnostics_widget)
        layout.addWidget(status_group)

        takes_group = QGroupBox("Take Review")
        takes_layout = QVBoxLayout(takes_group)
        header = QHBoxLayout()
        self.take_track_combo = QComboBox()
        self.take_track_combo.currentIndexChanged.connect(self.refresh_take_review_list)
        self.take_sort_combo = QComboBox()
        self.take_sort_combo.addItem("Newest First", "newest")
        self.take_sort_combo.addItem("Oldest First", "oldest")
        self.take_sort_combo.currentIndexChanged.connect(self.on_take_review_preferences_changed)
        self.take_filter_combo = QComboBox()
        self.take_filter_combo.addItem("All Takes", "all")
        self.take_filter_combo.addItem("Clipped Only", "clipped")
        self.take_filter_combo.addItem("Active Only", "active")
        self.take_filter_combo.currentIndexChanged.connect(self.on_take_review_preferences_changed)
        self.take_view_mode_combo = QComboBox()
        self.take_view_mode_combo.addItem("Expanded", "expanded")
        self.take_view_mode_combo.addItem("Compact", "compact")
        self.take_view_mode_combo.currentIndexChanged.connect(self.on_take_review_preferences_changed)
        self.take_loop_combo = QComboBox()
        self.take_loop_combo.addItem("One-Shot", False)
        self.take_loop_combo.addItem("Loop", True)
        self.take_loop_combo.currentIndexChanged.connect(self.on_take_review_preferences_changed)
        self.hide_inactive_take_clips_btn = QPushButton("\U0001f441")
        self.hide_inactive_take_clips_btn.setCheckable(True)
        self._configure_symbol_button(self.hide_inactive_take_clips_btn, "\U0001f441", "Hide inactive takes")
        self.hide_inactive_take_clips_btn.toggled.connect(self.on_hide_inactive_take_clips_toggled)
        for widget in [QLabel("Track"), self.take_track_combo, self.take_sort_combo, self.take_filter_combo, self.take_view_mode_combo, self.take_loop_combo, self.hide_inactive_take_clips_btn]:
            header.addWidget(widget)
        refresh_takes_btn = QPushButton("\u21bb")
        self._configure_symbol_button(refresh_takes_btn, "\u21bb", "Refresh takes")
        refresh_takes_btn.clicked.connect(self.refresh_take_review_list)
        header.addWidget(refresh_takes_btn)
        header.addStretch()
        takes_layout.addLayout(header)

        self.take_list_widget = TakeListWidget()
        self.take_review_list = self.take_list_widget.list_widget
        self.take_list_widget.on_item_double_clicked(self.audition_selected_take)
        takes_layout.addWidget(self.take_list_widget)

        take_actions = QGridLayout()
        take_actions.setHorizontalSpacing(4)
        take_actions.setVerticalSpacing(4)
        for index, (symbol, slot, tip) in enumerate([
            ("\u2713", self.set_selected_take_active, "Set selected take as active"),
            ("\u25b6", self.audition_selected_take, "Audition selected take"),
            ("\u25b7", self.audition_active_take, "Audition active take"),
            ("\u25a0", self.stop_take_audition, "Stop take audition"),
            ("\u2715", self.delete_selected_take, "Delete selected take"),
            ("\u2605", self.toggle_selected_take_keeper, "Toggle keeper on selected take"),
            ("\U0001f507", self.toggle_selected_take_muted, "Toggle mute on selected take"),
            ("-", lambda: self.rate_selected_take(-1), "Lower selected take rating"),
            ("+", lambda: self.rate_selected_take(1), "Raise selected take rating"),
            ("\U0001f3c6", self.use_best_take_for_selected_track, "Use best take for selected track"),
        ]):
            button = QPushButton(symbol)
            self._configure_symbol_button(button, symbol, tip)
            button.clicked.connect(slot)
            take_actions.addWidget(button, index // 5, index % 5)
        takes_layout.addLayout(take_actions)
        layout.addWidget(takes_group, stretch=1)

        comp_group = QGroupBox("Comping and Recovery")
        comp_layout = QGridLayout(comp_group)
        self.comp_start_sec_input = QLineEdit()
        self.comp_end_sec_input = QLineEdit()
        self.recovery_history_combo = QComboBox()
        comp_layout.addWidget(QLabel("Comp Start"), 0, 0)
        comp_layout.addWidget(self.comp_start_sec_input, 0, 1)
        comp_layout.addWidget(QLabel("Comp End"), 0, 2)
        comp_layout.addWidget(self.comp_end_sec_input, 0, 3)
        button_row = QHBoxLayout()
        button_row.setSpacing(4)
        for symbol, slot, tip in [
            ("\u239a", self.create_comp_region_from_selection, "Create comp region from selection"),
            ("\u21a6", self.assign_selected_take_to_comp_region, "Assign selected take to comp region"),
            ("\u232b", self.clear_comp_region_from_selection, "Clear comp region"),
            ("\u21bb", self.refresh_recovery_history, "Refresh recovery history"),
            ("\u21ba", self.restore_selected_recovery_snapshot, "Restore selected recovery snapshot"),
        ]:
            button = QPushButton(symbol)
            self._configure_symbol_button(button, symbol, tip)
            button.clicked.connect(slot)
            button_row.addWidget(button)
        button_row.addStretch()
        comp_layout.addLayout(button_row, 1, 0, 1, 4)
        comp_layout.addWidget(QLabel("Recovery History"), 2, 0)
        comp_layout.addWidget(self.recovery_history_combo, 2, 1, 1, 3)
        layout.addWidget(comp_group)

        meters_group = QGroupBox("Input Levels")
        meters_layout = QVBoxLayout(meters_group)
        self.meter_container = QVBoxLayout()
        self._build_recording_meters()
        meters_layout.addLayout(self.meter_container)
        layout.addWidget(meters_group)

        return tab

    def _build_voice_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        effect_group = QGroupBox("Voice Conversion")
        effect_layout = QGridLayout(effect_group)
        self.voice_track_index_input = QLineEdit()
        self.voice_track_index_input.setToolTip("Zero-based track index containing the clip to process")
        self.voice_clip_id_input = QLineEdit()
        self.voice_clip_id_input.setToolTip("Numeric ID of the clip to apply voice conversion to")

        # Editable ComboBox pre-populated with available voice profiles
        self.voice_profile_combo = QComboBox()
        self.voice_profile_combo.setEditable(True)
        self.voice_profile_combo.setToolTip("Select an existing voice profile or type a name")
        self._populate_voice_profile_combo()
        # Expose as voice_profile_name_input so the base class apply_voice_effect_to_clip works
        self.voice_profile_name_input = self.voice_profile_combo.lineEdit()

        effect_layout.addWidget(QLabel("Track"), 0, 0)
        effect_layout.addWidget(self.voice_track_index_input, 0, 1)
        effect_layout.addWidget(QLabel("Clip ID"), 0, 2)
        effect_layout.addWidget(self.voice_clip_id_input, 0, 3)
        effect_layout.addWidget(QLabel("Voice Profile"), 1, 0)
        effect_layout.addWidget(self.voice_profile_combo, 1, 1, 1, 3)
        apply_btn = QPushButton("Apply Voice Effect")
        apply_btn.setToolTip("Apply the selected voice conversion to the specified clip")
        apply_btn.clicked.connect(self.apply_voice_effect_to_clip)
        manage_btn = QPushButton("Manage Voices")
        manage_btn.setToolTip("Open the Voice Manager to record or import voice profiles")
        manage_btn.clicked.connect(self.open_voice_manager)
        effect_layout.addWidget(apply_btn, 2, 2)
        effect_layout.addWidget(manage_btn, 2, 3)
        layout.addWidget(effect_group)
        return tab

    def _populate_voice_profile_combo(self) -> None:
        """Refresh the voice profile ComboBox from stored profiles."""
        current_text = self.voice_profile_combo.currentText()
        self.voice_profile_combo.blockSignals(True)
        self.voice_profile_combo.clear()
        for profile in load_voice_profiles():
            self.voice_profile_combo.addItem(profile.name)
        self.voice_profile_combo.blockSignals(False)
        if current_text:
            idx = self.voice_profile_combo.findText(current_text)
            if idx >= 0:
                self.voice_profile_combo.setCurrentIndex(idx)
            else:
                self.voice_profile_combo.setCurrentText(current_text)

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
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        stems_group = QGroupBox("Project Tools")
        stems_layout = QHBoxLayout(stems_group)
        stems_btn = QPushButton("Split Song into Stems")
        stems_btn.clicked.connect(self.split_song_into_stems)
        self._configure_symbol_button(stems_btn, "\u2702", "Split song into stems")
        stems_layout.addWidget(stems_btn)
        layout.addWidget(stems_group)

        layout.addStretch()
        return tab

    def _build_help_tab(self) -> QWidget:
        """Build the built-in user's guide tab."""
        tab = QWidget()
        root = QVBoxLayout(tab)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Search bar
        search_row = QHBoxLayout()
        search_lbl = QLabel("Search:")
        search_row.addWidget(search_lbl)
        self._help_search = QLineEdit()
        self._help_search.setPlaceholderText("Type to search the guide…")
        self._help_search.setToolTip("Filter the guide to show only sections matching your search term")
        self._help_search.textChanged.connect(self._filter_help_text)
        search_row.addWidget(self._help_search, stretch=1)
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(60)
        clear_btn.setToolTip("Clear the search filter")
        clear_btn.clicked.connect(self._help_search.clear)
        search_row.addWidget(clear_btn)
        root.addLayout(search_row)

        self._help_view = QTextEdit()
        self._help_view.setReadOnly(True)
        self._help_view.setStyleSheet(
            "QTextEdit { background:#0d1b2a; color:#dde1e7; border:1px solid #0f3460; "
            "font-size:12px; line-height:1.4; }"
        )
        self._help_full_html = self._help_guide_html()
        self._help_view.setHtml(self._help_full_html)
        root.addWidget(self._help_view, stretch=1)
        return tab

    def _filter_help_text(self, query: str) -> None:
        query = query.strip()
        if not query:
            self._help_view.setHtml(self._help_full_html)
            return
        lower_q = query.lower()
        # Split HTML into sections at each h2/h3 opening tag. The positive lookahead
        # (?=<h[23]) keeps the tag itself in each section rather than consuming it.
        import re
        sections = re.split(r'(?=<h[23])', self._help_full_html)
        matching = [s for s in sections if lower_q in s.lower()]
        if matching:
            self._help_view.setHtml("".join(matching))
        else:
            self._help_view.setHtml(
                f'<p style="color:#e94560;">No sections found matching "<b>{query}</b>". '
                f'Try a different keyword.</p>'
            )

    @staticmethod
    def _help_guide_html() -> str:
        return """
<style>
  body  { background:#0d1b2a; color:#dde1e7; font-family:'Segoe UI',Arial,sans-serif; font-size:12px; }
  h2    { color:#e94560; border-bottom:1px solid #0f3460; padding-bottom:4px; margin-top:18px; }
  h3    { color:#64b5f6; margin-top:12px; margin-bottom:4px; }
  p     { margin:4px 0 8px 0; }
  ul    { margin:4px 0 8px 16px; }
  li    { margin-bottom:3px; }
  code  { background:#0f3460; color:#80cbc4; padding:1px 4px; border-radius:3px; }
  kbd   { background:#0f3460; border:1px solid #1a4080; border-radius:3px;
          padding:1px 5px; font-size:11px; }
  .tip  { background:#0f3460; border-left:3px solid #e94560; padding:6px 10px; margin:8px 0; }
</style>

<h2>Echo Pro — User Guide</h2>
<p>Welcome to <b>Echo Pro</b>, an integrated digital audio workstation for recording,
mixing, voice cloning, and AI-assisted music generation.</p>

<h2>Getting Started</h2>
<h3>First Launch</h3>
<ul>
  <li>On first launch the <b>First Run Setup</b> dialog helps you verify audio drivers and
      install optional AI backends (Demucs for stem separation, music generation models).</li>
  <li>You can rerun setup at any time via <b>Tools → Install / Update Dependencies</b>.</li>
</ul>
<h3>Creating a Project</h3>
<ul>
  <li>Use the hover-labeled top toolbar icons to create, open, save, or browse projects.</li>
  <li>The <b>+</b> button starts a fresh project.</li>
  <li>The folder button opens a previously saved <code>.json</code> project file.</li>
  <li>The disk button writes the current project to disk, and the search button opens the project browser.</li>
</ul>

<h2>Home Tab</h2>
<p>The Home tab is your main mixing and arrangement workspace.</p>
<h3>Master Stereo Output</h3>
<p>Shows a symbolic stereo waveform for the master bus. A live level meter is available
after playback.</p>
<h3>Project Actions</h3>
<p>Use the hover-labeled icon buttons in this panel to add, rename, delete, reorder, mute,
solo, and arm tracks. Type a name in the text box first, then use the <b>+</b> button to add
the track.</p>
<h3>Audio and Track Tools</h3>
<ul>
  <li><b>Clip import icon button</b> — enter a track index and optional start time, then use the
      hover-labeled folder button to browse for a WAV/MP3/FLAC/OGG file.</li>
  <li><b>Track volume icon button</b> — enter a track index and a dB value (e.g. <code>-6</code>,
      <code>0</code>, <code>+3</code>) and use the hover-labeled speaker button to apply it.</li>
  <li><b>Transport icon buttons</b> — use the hover labels on the play, stop, jump-start, and jump-end buttons to control playback from the current Home-tab playhead.</li>
</ul>
<h3>Stem Splitting (Demucs)</h3>
<ul>
  <li><b>Choose Source Audio</b> — select the full mix you want Demucs to split into stems.</li>
  <li><b>Demucs Model</b> — switch between the balanced 4-stem, fine-tuned 4-stem, and 6-stem presets before starting the split.</li>
  <li><b>Backend and status area</b> — confirms whether Demucs/ffmpeg are ready and keeps recent launch, progress, and completion messages visible.</li>
  <li><b>Run Demucs Split</b> — starts the split for the selected source and adds the resulting stems to the current project.</li>
</ul>
<div class="tip"><b>Tip:</b> All sections on the Home tab can be collapsed with the
<b>▼ / ▶</b> toggle button on their header bar, giving you more room for the waveform
editor and mixer. The waveform and mixer panels are separated by a draggable splitter —
drag it to resize.</div>
<h3>Waveforms (Timeline)</h3>
<ul>
  <li>Each track row shows its clips with a waveform preview.</li>
  <li><b>Left-click</b> a clip to select it; selected clips are highlighted in yellow.</li>
  <li><b>Drag</b> a selected clip to move it along the timeline.</li>
  <li><b>Right-click</b> on an empty part of a track row to add a new clip at that
      position — a file browser will open automatically.</li>
  <li><b>Right-click</b> on an existing clip to select or delete it.</li>
  <li>Press <kbd>Del</kbd> or <kbd>Backspace</kbd> to delete the selected clip.</li>
  <li>Click-drag on an empty area of the currently selected track to define a
      <b>comp range</b> for take comping.</li>
  <li>The red vertical line shows the current playhead position used by the Home-tab transport controls.</li>
</ul>
<h3>Studio Mixer</h3>
<p>Each track has its own vertical channel strip containing:</p>
<ul>
  <li><b>7-band EQ sliders</b> (40 Hz – 16 kHz, ±12 dB)</li>
  <li><b>Vertical gain fader</b> (−60 dB to +6 dB)</li>
  <li><b>Pan knob</b> (left ↔ right)</li>
  <li><b>Punch / Mute / Solo</b> buttons</li>
  <li><b>Stereo L/R level meters</b></li>
</ul>
<p>Scroll horizontally to see all channel strips when you have many tracks.</p>

<h2>Recording Tab</h2>
<h3>Audio Devices</h3>
<ul>
  <li>Select your <b>Input</b> (microphone/interface) and <b>Output</b> (speakers/headphones)
      from the dropdowns.</li>
  <li>Choose a <b>Sample Rate</b> (44.1 kHz, 48 kHz, 88.2 kHz, or 96 kHz).</li>
  <li>Use the hover-labeled refresh and speaker buttons to re-scan or test the selected audio devices.</li>
</ul>
<h3>Recording Controls</h3>
<ul>
  <li>Use the hover-labeled icon buttons to arm tracks, apply BPM, time signature, and count-in settings.</li>
  <li>Select a target track in the <b>Arm track</b> field and use the record transport button to start recording.</li>
  <li>Use the stop transport button to finish. Each recording becomes a <em>take</em>.</li>
  <li>Enable <b>Punch In / Punch Out</b> to record only within a defined time range.</li>
</ul>
<h3>Take Review</h3>
<p>After recording you can listen to each take, mark one as active, or comp multiple takes
together using the <b>Comp Range</b> tool in the timeline. The take review and comp/recovery action rows now use hover-labeled icon buttons for refresh, audition, rating, keeper/mute, and recovery operations.</p>

<h2>Voice FX Tab</h2>
<h3>Voice Manager</h3>
<p>Click <b>Manage Voices</b> to open the Voice Manager dialog:</p>
<ul>
  <li>Enter a <b>profile name</b>.</li>
  <li>Choose a <b>clip duration</b> (longer recordings improve model accuracy).</li>
  <li>Optionally paste a <b>speaking script</b> to read aloud during recording.</li>
  <li>Click <b>Record</b> to capture your voice, or <b>Import Audio File</b> to use an
      existing WAV/MP3.</li>
</ul>
<h3>Applying Voice Effects</h3>
<ul>
  <li>Select a voice profile from the editable <b>Voice Profile</b> combo box (or type
      a custom name).</li>
  <li>Choose the target clip and click <b>Apply Voice Effect</b>.</li>
</ul>

<h2>Music Tab</h2>
<ul>
  <li>Enter a text <b>prompt</b> describing the style or mood of the music.</li>
  <li>Set the desired <b>duration</b> in seconds (10–30 s recommended).</li>
  <li>Click <b>Generate Music</b>. A progress dialog will appear while the AI backend
      creates the clip.</li>
  <li>Use <b>Plan Song Sections</b> to have the AI suggest a multi-section arrangement.</li>
  <li>Generated clips are automatically added to the project for mixing.</li>
</ul>

<h2>Tools Tab</h2>
<ul>
  <li><b>Split Song into Stems</b> — reuses the selected Home-tab source audio when available, or prompts for one before running Demucs.</li>
  <li><b>Install / Update Dependencies</b> — re-runs the installer for AI backends.</li>
</ul>

<h2>Keyboard Shortcuts</h2>
<ul>
  <li><kbd>Del</kbd> / <kbd>Backspace</kbd> — delete selected timeline clip</li>
  <li><b>Left-click drag</b> on a clip — move clip along the timeline</li>
  <li><b>Right-click</b> on timeline — context menu (add clip / delete clip)</li>
  <li><b>▼ / ▶</b> buttons — collapse / expand any panel on the Home tab</li>
</ul>

<h2>Tips &amp; Best Practices</h2>
<ul>
  <li>Record longer voice samples (30 s or more) for better voice cloning quality.</li>
  <li>Use a phonetically rich script in the Voice Manager for more accurate models.</li>
  <li>Keep individual track volumes near 0 dB and adjust the master output instead to
      avoid clipping.</li>
  <li>Use <b>Solo</b> to listen to a single track in isolation while mixing.</li>
  <li>Stem separation works best on full-mix stereo WAV files at 44.1 kHz or 48 kHz.</li>
  <li>Save your project frequently — use <kbd>Ctrl+S</kbd> if your OS forwards it,
      or click the <b>Save</b> button in the toolbar.</li>
</ul>
"""



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
                on_mute_toggle=self._set_track_muted,
                on_solo_toggle=self._set_track_soloed,
                on_open_playback_settings=self._open_track_playback_settings,
            )
            row.set_volume_db(track.volume_db)
            row.set_mute(track.muted)
            row.set_solo(track.soloed)
            summary, tooltip = self._track_playback_summary(track)
            row.set_playback_summary(summary, tooltip)
            self.mixer_layout.insertWidget(self.mixer_layout.count() - 1, row)
            self.mixer_rows.append(row)

    def _on_track_volume_changed(self, track_index: int, db: float) -> None:
        if 0 <= track_index < len(self.current_project.tracks):
            self.current_project.tracks[track_index].volume_db = db
            self.sync_project_tracks_to_recording_engine()
            self.update_status(f"Track {track_index + 1} volume: {db:+.0f} dB")

    def _set_track_muted(self, track_index: int, muted: bool) -> None:
        if 0 <= track_index < len(self.current_project.tracks):
            self.current_project.tracks[track_index].muted = bool(muted)
            self.sync_project_tracks_to_recording_engine()
            self.refresh_track_list()

    def _set_track_soloed(self, track_index: int, soloed: bool) -> None:
        if 0 <= track_index < len(self.current_project.tracks):
            self.current_project.tracks[track_index].soloed = bool(soloed)
            self.sync_project_tracks_to_recording_engine()
            self.refresh_track_list()

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
        self.update_status(f"Updated playback settings for track {track_index + 1}")

    def refresh_track_list(self):
        super().refresh_track_list()
        self._rebuild_mixer_rows()

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


EchoProWindow = TabbedEchoProWindow

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
