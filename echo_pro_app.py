
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
    QStatusBar, QPushButton, QFileDialog, QHBoxLayout, QLineEdit,
    QComboBox,
    QMessageBox, QDialog, QTextEdit, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QTimer

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
from audio_device import device_manager

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

        self.recording_status_label = QLabel("Recording: idle")
        recording_layout.addWidget(self.recording_status_label)

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
        self.cloud_enabled.setPlaceholderText("Cloud? yes/no")
        cloud_layout.addWidget(self.cloud_enabled)
        layout.addLayout(cloud_layout)

        # Timeline
        self.timeline = TimelineWidget(self.current_project)
        layout.addWidget(self.timeline)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.refresh_track_list()
        self.refresh_audio_device_selectors()
        self.sync_project_tracks_to_recording_engine()
        self.sync_recording_controls_from_controller()
        self.update_recording_status_label()

        self.update_status("Ready")

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
        self.recording_status_label.setText(
            f"Recording: {state} | Tempo: {status.current_tempo_bpm} BPM | Time Sig: {status.time_signature} | Count-In: {count_in_bars} bar(s) | Armed: {armed_text}"
        )

    def sync_recording_controls_from_controller(self):
        self.record_tempo_input.setText(str(self.recording_controller.status.current_tempo_bpm))
        self.record_time_sig_input.setText(self.recording_controller.status.time_signature)
        self.record_count_in_input.setText(str(self.recording_controller.metronome.config.count_in_bars))

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
        text = self.record_time_sig_input.text().strip()
        if "/" not in text:
            QMessageBox.warning(self, "Input error", "Time signature must look like 4/4.")
            return

        parts = text.split("/", 1)
        try:
            numerator = int(parts[0].strip())
            denominator = int(parts[1].strip())
        except ValueError:
            QMessageBox.warning(self, "Input error", "Time signature values must be numbers.")
            return

        if numerator <= 0 or denominator <= 0:
            QMessageBox.warning(self, "Input error", "Time signature values must be positive.")
            return

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

        self.transport_bar.record_button.setEnabled(False)
        self.transport_bar.stop_button.setEnabled(True)
        self.update_status(f"Recording started (Input {selected_input}, Output {selected_output})")
        self.update_recording_status_label()

    def stop_recording_session(self):
        if self.recording_controller.status.is_recording or self.recording_controller.status.count_in_active:
            self.recording_controller.stop_recording(duration_seconds=0.0, level_stats={})
            self.recording_controller.stop_stream()

        self.transport_bar.record_button.setEnabled(True)
        self.transport_bar.stop_button.setEnabled(False)
        self.transport_bar.click_button.setText("Metronome On")
        self.update_status("Recording stopped")
        self.update_recording_status_label()

    def undo_last_recording_take(self):
        take = self.recording_controller.undo_last_take()
        if take is None:
            self.update_status("Nothing to undo")
        else:
            self.update_status(f"Undid take {take.take_number} on track {take.track_id}")
        self.update_recording_status_label()

    def redo_last_recording_take(self):
        take = self.recording_controller.redo_last_take()
        if take is None:
            self.update_status("Nothing to redo")
        else:
            self.update_status(f"Redid take {take.take_number} on track {take.track_id}")
        self.update_recording_status_label()

    def update_status(self, text: str):
        self.status.showMessage(text)

    def refresh_timeline(self):
        self.timeline.set_project(self.current_project)
        self.timeline.set_selected_track(self.selected_track_index)
        self.timeline.update()

    def new_project(self):
        self.current_project = new_empty_project("Untitled")
        self.project_name_label.setText("Project: Untitled")
        self.next_clip_id = 1
        self.last_song_generation = None
        self.recording_controller = RecordingController("new_session", self.current_project.name)
        self.selected_track_index = None
        self.sync_project_tracks_to_recording_engine()
        self.sync_recording_controls_from_controller()
        self._build_recording_meters()
        self.refresh_track_list()
        self.update_recording_status_label()
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
            self.last_song_generation = None
            max_id = 0
            for c in proj.clips:
                if c.id > max_id:
                    max_id = c.id
            self.next_clip_id = max_id + 1
            self.recording_controller = RecordingController(f"session_{proj.name.replace(' ', '_')}", proj.name)
            self.selected_track_index = None
            self.sync_project_tracks_to_recording_engine()
            self.sync_recording_controls_from_controller()
            self._build_recording_meters()
            self.refresh_track_list()
            self.update_recording_status_label()
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
                self.last_song_generation = None
                max_id = 0
                for c in proj.clips:
                    if c.id > max_id:
                        max_id = c.id
                self.next_clip_id = max_id + 1
                self.recording_controller = RecordingController(f"session_{proj.name.replace(' ', '_')}", proj.name)
                self.selected_track_index = None
                self.sync_project_tracks_to_recording_engine()
                self.sync_recording_controls_from_controller()
                self._build_recording_meters()
                self.refresh_track_list()
                self.update_recording_status_label()
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
        try:
            track_index = int(self.clip_track_index_input.text())
        except ValueError:
            QMessageBox.warning(self, "Input error", "Track index must be a number (0, 1, 2, ...).")
            return
        if track_index < 0 or track_index >= len(self.current_project.tracks):
            QMessageBox.warning(self, "Input error", "Track index out of range.")
            return

        try:
            start_sec = float(self.clip_start_sec_input.text())
        except ValueError:
            start_sec = 0.0

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choose audio file for clip",
            "",
            "Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)"
        )
        if not filename:
            return

        try:
            length_ms = get_audio_length_ms(filename)
            start_ms = int(start_sec * 1000)
            clip = Clip(
                id=self.next_clip_id,
                track_index=track_index,
                file_path=filename,
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
        try:
            track_index = int(self.volume_track_index_input.text())
        except ValueError:
            QMessageBox.warning(self, "Input error", "Track index must be a number.")
            return
        if track_index < 0 or track_index >= len(self.current_project.tracks):
            QMessageBox.warning(self, "Input error", "Track index out of range.")
            return

        try:
            db = float(self.volume_db_input.text())
        except ValueError:
            QMessageBox.warning(self, "Input error", "Volume must be a number (decibels).")
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

        try:
            song_path = Path(filename)
            stems_root = song_path.parent / "echo_stems"
            song_stems_dir = stems_root / song_path.stem

            self.update_status("Running Demucs... this may take a while.")
            QApplication.processEvents()

            stems = separate_stems(str(song_path), song_stems_dir)

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
                "A placeholder voice conversion was applied.\n"
                "In the future, this will use a real model without changing this UI."
            )
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
            self.update_status("Generated clip added to project.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate clip:\n{e}")

    def generate_full_song(self):
        try:
            total_length_sec = int(self.plan_total_length.text())
            structure = [s.strip() for s in self.plan_structure.text().split(",") if s.strip()]
            if not structure:
                QMessageBox.warning(self, "Input error", "Enter at least one section in the structure.")
                return

            key = self.plan_key.text()
            chords = self.plan_chords.text()
            time_sig = self.plan_time_sig.text()
            tempo = int(self.plan_tempo.text())
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