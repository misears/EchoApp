
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
    QStatusBar, QPushButton, QFileDialog, QHBoxLayout, QLineEdit,
    QComboBox, QProgressDialog,
    QMessageBox, QDialog, QTextEdit, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QTimer

from project_model import Project, Track, Clip, new_empty_project, save_project, load_project
from audio_info import get_audio_length_ms
from timeline_widget import TimelineWidget
from playback_mixer import play_project
from stems_engine import (
    StemCancelledError,
    StemDependencyError,
    StemSeparationError,
    add_stems_to_project,
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
from recording_ui_components import TrackMeterWidget, TransportBar, RecordingDiagnosticsWidget
from audio_device import device_manager
from p5a_regression_runner import format_regression_summary, run_phase5a_regression_checks
from recording_recovery import RecoverySnapshotManager
from input_validation import parse_float, parse_int, parse_time_signature, run_common_validation_checks

class FirstRunDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Welcome to Echo Pro")

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

        layout = QVBoxLayout()

        self.list_box = QTextEdit()
        self.list_box.setReadOnly(True)

        projects = []
        for f in PROJECTS_DIR.glob("*.eproj"):
            projects.append(str(f))
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
        profiles = load_voice_profiles()
        for p in profiles:
            item = QListWidgetItem(f"{p.name} [{p.file_path}]")
            item.setData(Qt.UserRole, p)
            self.voice_list.addItem(item)

    def record_new_voice(self):
        name = self.new_voice_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Input error", "Please enter a name for the voice profile.")
            return

        confirm = QMessageBox.question(
            self,
            "Consent confirmation",
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
        self.recording_controller.restore_session_preferences()
        self.recovery_manager = RecoverySnapshotManager()
        self.recording_meters = {}
        self.selected_track_index = None
        self.selected_input_device_id = None
        self.selected_output_device_id = None
        self.last_song_generation = None

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.recording_timer = QTimer(self)
        self.recording_timer.setInterval(100)
        self.recording_timer.timeout.connect(self.refresh_recording_meters)
        self.recording_timer.start()

        layout = QVBoxLayout()

        # Top bar
        top_layout = QHBoxLayout()
        self.project_name_label = QLabel("Project: Untitled")
        top_layout.addWidget(self.project_name_label)

        new_btn = QPushButton("New Project")
        new_btn.clicked.connect(self.new_project)
        top_layout.addWidget(new_btn)

        open_btn = QPushButton("Open Project")
        open_btn.clicked.connect(self.open_project)
        top_layout.addWidget(open_btn)

        save_btn = QPushButton("Save Project")
        save_btn.clicked.connect(self.save_project_dialog)
        top_layout.addWidget(save_btn)

        browser_btn = QPushButton("Browse Projects")
        browser_btn.clicked.connect(self.browse_projects)
        top_layout.addWidget(browser_btn)

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

        play_btn = QPushButton("Play Project")
        play_btn.clicked.connect(self.play_current_project)
        vol_layout.addWidget(play_btn)

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
        run_p5a_checks_btn = QPushButton("Run P5A Checks")
        run_p5a_checks_btn.clicked.connect(self.run_p5a_regression_checks)

        device_row.addWidget(QLabel("Input"))
        device_row.addWidget(self.input_device_combo)
        device_row.addWidget(QLabel("Output"))
        device_row.addWidget(self.output_device_combo)
        device_row.addWidget(refresh_devices_btn)
        device_row.addWidget(test_devices_btn)
        device_row.addWidget(run_p5a_checks_btn)
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

        self.pre_roll_bar_input = QLineEdit()
        self.pre_roll_bar_input.setPlaceholderText("Pre-Roll (bars)")
        timing_row.addWidget(self.pre_roll_bar_input)

        self.post_roll_bar_input = QLineEdit()
        self.post_roll_bar_input.setPlaceholderText("Post-Roll (bars)")
        timing_row.addWidget(self.post_roll_bar_input)

        set_roll_btn = QPushButton("Set Pre/Post")
        set_roll_btn.clicked.connect(self.set_recording_pre_post_roll)
        timing_row.addWidget(set_roll_btn)

        self.punch_mode_combo = QComboBox()
        self.punch_mode_combo.addItem("Punch Off", False)
        self.punch_mode_combo.addItem("Punch On", True)
        self.punch_mode_combo.currentIndexChanged.connect(self.on_punch_mode_changed)
        timing_row.addWidget(self.punch_mode_combo)

        self.punch_in_bar_input = QLineEdit()
        self.punch_in_bar_input.setPlaceholderText("Punch In (bars)")
        timing_row.addWidget(self.punch_in_bar_input)

        self.punch_out_bar_input = QLineEdit()
        self.punch_out_bar_input.setPlaceholderText("Punch Out (bars)")
        timing_row.addWidget(self.punch_out_bar_input)

        set_punch_btn = QPushButton("Set Punch")
        set_punch_btn.clicked.connect(self.set_recording_punch_range)
        timing_row.addWidget(set_punch_btn)

        self.loop_mode_combo = QComboBox()
        self.loop_mode_combo.addItem("Loop Off", False)
        self.loop_mode_combo.addItem("Loop On", True)
        self.loop_mode_combo.currentIndexChanged.connect(self.on_loop_mode_changed)
        timing_row.addWidget(self.loop_mode_combo)

        self.loop_start_bar_input = QLineEdit()
        self.loop_start_bar_input.setPlaceholderText("Loop Start (bars)")
        timing_row.addWidget(self.loop_start_bar_input)

        self.loop_end_bar_input = QLineEdit()
        self.loop_end_bar_input.setPlaceholderText("Loop End (bars)")
        timing_row.addWidget(self.loop_end_bar_input)

        set_loop_btn = QPushButton("Set Loop")
        set_loop_btn.clicked.connect(self.set_recording_loop_range)
        timing_row.addWidget(set_loop_btn)

        recording_layout.addLayout(timing_row)

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

        refresh_takes_btn = QPushButton("Refresh Takes")
        refresh_takes_btn.clicked.connect(self.refresh_take_review_list)
        take_review_header.addWidget(refresh_takes_btn)
        recording_layout.addLayout(take_review_header)

        self.take_review_list = QListWidget()
        self.take_review_list.itemDoubleClicked.connect(self.audition_selected_take)
        recording_layout.addWidget(self.take_review_list)

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

        apply_voice_btn = QPushButton("Apply Voice Effect (Placeholder)")
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

        self.update_status("Ready")

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

    def _build_recording_meters(self):
        while self.meter_container.count():
            item = self.meter_container.takeAt(0)
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

        hide_inactive = bool(prefs.get("hide_inactive_take_clips", False))
        self.hide_inactive_take_clips_btn.setChecked(hide_inactive)
        self.timeline.set_hide_inactive_take_clips(hide_inactive)

    def on_take_review_preferences_changed(self, *_args):
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
            self.take_review_list.item(0).setFlags(Qt.NoItemFlags)
            return

        for take in takes:
            peak_db = float(take.level_stats.get("peak", -80.0))
            clipping = float(take.level_stats.get("clipping", 0.0)) >= 0.5
            status = "ACTIVE" if take.used else "inactive"
            timestamp = take.timestamp.replace("T", " ")[:19]
            clip_flag = "CLIP" if clipping else "OK"
            keeper_flag = "KEEP" if bool(getattr(take, "is_keeper", False)) else "----"
            muted_flag = "MUTED" if bool(getattr(take, "is_muted", False)) else "AUD"
            rating = int(getattr(take, "rating", 0))
            text = (
                f"Take {take.take_number} [{status}] | {take.duration_seconds:.2f}s"
                f" | Peak {peak_db:.1f} dB | {clip_flag} | {keeper_flag} | {muted_flag} | R{rating} | {timestamp}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, {"track_id": int(track_id), "take_number": take.take_number})
            self.take_review_list.addItem(item)

    def _get_selected_take(self):
        track_id, take_number = self._selected_take_ref()
        if track_id is None or take_number is None:
            return None, None, None
        take = self.recording_controller.session.get_take(int(track_id), int(take_number))
        return int(track_id), int(take_number), take

    def _selected_take_ref(self):
        item = self.take_review_list.currentItem()
        if item is None:
            return None, None
        data = item.data(Qt.UserRole)
        if not isinstance(data, dict):
            return None, None
        return data.get("track_id"), data.get("take_number")

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
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
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
        if take is None:
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
        if take is None:
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
        if take is None:
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

    def _clear_recovery_snapshot(self) -> None:
        self.recovery_manager.clear_snapshot(self.recording_controller.session.session_id)

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
        return True

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
            QMessageBox.Yes | QMessageBox.No,
        )

        if choice == QMessageBox.Yes:
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
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
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
            self.transport_bar.click_button.setText("Metronome On")
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

        ok, message = device_manager.test_device_configuration()
        summary = device_manager.get_device_summary()
        details = (
            f"Input: {summary['input_device']}\n"
            f"Output: {summary['output_device']}\n"
            f"Sample Rate: {summary['sample_rate']} Hz\n"
            f"Buffer Size: {summary['buffer_size']}\n"
            f"Input Latency: {summary['input_latency_ms']:.1f} ms\n"
            f"Output Latency: {summary['output_latency_ms']:.1f} ms\n"
            f"Round Trip Latency: {summary['total_latency_ms']:.1f} ms"
        )

        if ok:
            QMessageBox.information(
                self,
                "Audio Device Test Passed",
                f"Result: {message}\n\n{details}",
            )
            self.update_status(f"Device test passed ({summary['total_latency_ms']:.1f} ms round trip)")
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

        if int(report.get("failed", 0)) == 0:
            QMessageBox.information(self, "P5A Regression Checks", summary)
        else:
            QMessageBox.warning(self, "P5A Regression Checks", summary)

        self.update_status(
            f"P5A regression checks complete: {report.get('passed', 0)} passed, {report.get('failed', 0)} failed"
        )

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
        self.transport_bar.click_button.setText("Metronome On")
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

    def refresh_timeline(self):
        self.timeline.set_project(self.current_project)
        self.timeline.set_selected_track(self.selected_track_index)
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
        self.current_project = new_empty_project("Untitled")
        self.project_name_label.setText("Project: Untitled")
        self.next_clip_id = 1
        self.last_song_generation = None
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
            proj = load_project(Path(filename))
            self.current_project = proj
            self.project_name_label.setText(f"Project: {proj.name}")
            self._restore_song_generation_metadata()
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
        if dlg.exec() == QDialog.Accepted and dlg.selected_path:
            filename = dlg.selected_path
            try:
                proj = load_project(Path(filename))
                self.current_project = proj
                self.project_name_label.setText(f"Project: {proj.name}")
                self._restore_song_generation_metadata()
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
            self,
            "Choose song to split into stems",
            "",
            "Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)"
        )
        if not filename:
            return
        song_path = Path(filename)
        if not song_path.exists():
            QMessageBox.warning(self, "Stems", "Selected song file does not exist.")
            return

        progress = QProgressDialog("Preparing stem separation...", "Cancel", 0, 0, self)
        progress.setWindowTitle("Stem separation")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        try:
            stems_root = song_path.parent / "echo_stems"
            song_stems_dir = stems_root / song_path.stem
            app_root = Path(__file__).resolve().parent
            local_demucs = app_root / "runtime" / "venv" / "Scripts" / "demucs.exe"
            local_ffmpeg = app_root / "tools" / "ffmpeg" / "current" / "bin" / "ffmpeg.exe"
            seed_demucs = app_root / "seeds" / "demucs" / "demucs.exe"
            seed_ffmpeg = app_root / "seeds" / "ffmpeg" / "bin" / "ffmpeg.exe"

            if local_demucs.exists():
                demucs_executable = str(local_demucs)
            elif seed_demucs.exists():
                demucs_executable = str(seed_demucs)
            else:
                demucs_executable = "demucs"

            if local_ffmpeg.exists():
                ffmpeg_executable = str(local_ffmpeg)
            elif seed_ffmpeg.exists():
                ffmpeg_executable = str(seed_ffmpeg)
            else:
                ffmpeg_executable = None

            self.update_status("Running Demucs... this may take a while.")
            QApplication.processEvents()

            def _progress_message(text: str) -> None:
                progress.setLabelText(text)
                QApplication.processEvents()

            stems = separate_stems(
                str(song_path),
                song_stems_dir,
                demucs_executable=demucs_executable,
                ffmpeg_executable=ffmpeg_executable,
                progress_callback=_progress_message,
                cancel_check=progress.wasCanceled,
            )

            self.next_clip_id = add_stems_to_project(
                self.current_project,
                stems,
                song_stems_dir,
                next_clip_id_start=self.next_clip_id
            )

            self.sync_project_tracks_to_recording_engine()
            self.refresh_track_list()
            self.refresh_timeline()
            self.update_status("Stems added to project.")
            QMessageBox.information(
                self,
                "Stems created",
                "Stems were created and added as tracks.\n"
                "You can now edit them on the timeline."
            )
        except StemCancelledError as e:
            QMessageBox.information(self, "Stems", str(e))
            self.update_status("Stems cancelled")
        except StemDependencyError as e:
            install_choice = QMessageBox.question(
                self,
                "Missing dependency",
                f"{e}\n\nRun dependency update now?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if install_choice == QMessageBox.Yes:
                script_path = Path(__file__).resolve().parent / "install_echo_pro.bat"
                subprocess.Popen([str(script_path), "update"], cwd=str(script_path.parent))
            self.update_status("Stems dependency issue")
        except StemSeparationError as e:
            QMessageBox.critical(self, "Error", f"Failed to split stems:\n{e}")
            self.update_status("Stems error")
        finally:
            progress.close()

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
                    f"{capability['reason']}\n\nGenerated clip uses placeholder output until assets are available.",
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
            self.update_status("Full song generated (placeholder clips).")
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

if __name__ == "__main__":
    run_common_validation_checks()
    app = QApplication(sys.argv)

    ensure_dirs()

    if is_first_run():
        dlg = FirstRunDialog()
        dlg.exec()
        mark_first_run_done()

    win = EchoProWindow()
    win.resize(1200, 700)
    win.show()
    sys.exit(app.exec())
