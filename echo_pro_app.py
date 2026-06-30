
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
    QStatusBar, QPushButton, QFileDialog, QHBoxLayout, QLineEdit,
    QMessageBox, QDialog, QTextEdit, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt

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

        self.status = QStatusBar()
        self.setStatusBar(self.status)

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
        track_layout = QHBoxLayout()
        self.new_track_name = QLineEdit()
        self.new_track_name.setPlaceholderText("New track name")
        track_layout.addWidget(self.new_track_name)

        add_track_btn = QPushButton("Add Track")
        add_track_btn.clicked.connect(self.add_track)
        track_layout.addWidget(add_track_btn)

        layout.addLayout(track_layout)

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

        self.update_status("Ready")

    def update_status(self, text: str):
        self.status.showMessage(text)

    def refresh_timeline(self):
        self.timeline.set_project(self.current_project)
        self.timeline.update()

    def new_project(self):
        self.current_project = new_empty_project("Untitled")
        self.project_name_label.setText("Project: Untitled")
        self.next_clip_id = 1
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
            max_id = 0
            for c in proj.clips:
                if c.id > max_id:
                    max_id = c.id
            self.next_clip_id = max_id + 1
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
                max_id = 0
                for c in proj.clips:
                    if c.id > max_id:
                        max_id = c.id
                self.next_clip_id = max_id + 1
                self.refresh_timeline()
                self.update_status(f"Opened project from library: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")

    def add_track(self):
        name = self.new_track_name.text().strip()
        if not name:
            name = f"Track {len(self.current_project.tracks)}"
        self.current_project.tracks.append(Track(name=name))
        self.new_track_name.clear()
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

            style = ""
            genre = ""
            mood = ""

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

            for path in clip_paths:
                length_ms = get_audio_length_ms(str(path))
                new_track_index = len(self.current_project.tracks)
                self.current_project.tracks.append(Track(name=f"Section {new_track_index}"))

                new_clip = Clip(
                    id=self.next_clip_id,
                    track_index=new_track_index,
                    file_path=str(path),
                    start_ms=0,
                    length_ms=length_ms
                )
                self.current_project.clips.append(new_clip)
                self.next_clip_id += 1

            self.refresh_timeline()
            self.update_status("Full song generated (placeholder clips).")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate full song:\n{e}")

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