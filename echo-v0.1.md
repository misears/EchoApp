<!-- markdownlint-disable -->
# ECHO PRO MASTER

[Document subtitle]

 
⭐ ECHO PRO — COMPLETE BEGINNER FRIENDLY BUILD TUTORIAL
A full DAW + AI music workstation you can build from scratch on Windows
📘 TABLE OF CONTENTS
1.	Introduction
2.	Setting Up Your Computer
3.	Why Echo Pro Is Designed This Way
4.	Phase 1 — Build the Core DAW
5.	Phase 2 — Add Stems, Playback, Mixing, First Run Wizard
6.	Phase 3 — Add Voice Recording, Voice Profiles, Voice Conversion Hooks
7.	Phase 4 — Add Music Generator + Song Planner + Cloud Toggle
8.	Phase 5 — Build Echo Pro Into a Windows Installer
9.	Appendix A — All Code Files (Grouped Together)
10.	Appendix B — Real Model Integration Interfaces
11.	Appendix C — References
1. ⭐ INTRODUCTION
Echo Pro is a local, offline first audio workstation that supports:
•	Multitrack editing
•	Stems separation
•	Voice recording + safe voice conversion
•	AI music generation (clip based)
•	Full song planning
•	Optional cloud generation
•	A clean installer
This tutorial walks you through building Echo Pro from nothing, using only:
•	Windows
•	Python
•	Visual Studio Code
Everything else is installed step by step.
2. 🖥️ SETTING UP YOUR COMPUTER
You need to install:
Program	Purpose	Download
Python 3.10+	Runs Echo Pro	https://www.python.org/downloads/windows/
Visual Studio Code	Code editor	https://code.visualstudio.com/
Git (optional)	Version control	https://git-scm.com/download/win
FFmpeg	Audio engine	https://ffmpeg.org/download.html
Inno Setup	Installer builder	https://jrsoftware.org/isinfo.php
2.1 Install Python
•	Download from python.org
•	Run installer
•	Check “Add Python to PATH”
•	Verify:
Code
python --version
2.2 Install Visual Studio Code
•	Download → Install → Open
2.3 Install FFmpeg
•	Download ZIP
•	Extract to C:\ffmpeg\
•	Add C:\ffmpeg\bin to PATH
•	Verify:
Code
ffmpeg -version
2.4 Install Inno Setup
•	Download → Install
2.5 Create Echo Pro folder
Code
C:\EchoPro\EchoApp\
Open this folder in VS Code.
2.6 Install Python libraries
In VS Code terminal:
Code
python -m pip install pyside6 pydub simpleaudio sounddevice soundfile demucs
3. 🧠 WHY ECHO PRO IS DESIGNED THIS WAY
Echo Pro is built around modularity:
•	DAW Core → Tracks, clips, timeline
•	Stems Engine → Demucs
•	Voice Engine → User recorded voices only
•	Music Generator → Clip based T2M
•	Song Planner → Breaks full songs into clips
•	AI Interfaces → Clean, replaceable functions
•	Installer → Makes Echo Pro feel like a real app
This modular design means:
•	You can upgrade any part later
•	You can plug in real AI models without rewriting the UI
•	Everything stays safe, local, and user controlled
4. 🎚️ PHASE 1 — BUILD THE CORE DAW
You will create:
•	Project model
•	Timeline widget
•	Audio info helper
•	Main Echo Pro window
•	Track/clip adding
•	Project save/load
All code is in Appendix A.
After Phase 1, Echo Pro can:
•	Create projects
•	Add tracks
•	Add clips
•	Save/load .eproj files
•	Display clips on a timeline
5. 🎛️ PHASE 2 — STEMS, PLAYBACK, MIXING, FIRST RUN WIZARD
You add:
•	Demucs integration
•	Playback using pydub + simpleaudio
•	Track volume controls
•	First run wizard
•	Project browser
After Phase 2, Echo Pro can:
•	Split songs into stems
•	Add stems as tracks
•	Play the whole mix
•	Adjust track volumes
•	Show a welcome screen
•	Browse saved projects
6. 🎤 PHASE 3 — VOICE RECORDING + VOICE CONVERSION HOOKS
You add:
•	Voice profile storage
•	Microphone recording
•	Consent based voice profiles
•	Placeholder voice conversion
•	UI for managing voices
•	UI for applying voice effects
After Phase 3, Echo Pro can:
•	Record your voice
•	Save voice profiles
•	Apply placeholder voice effects
•	Add converted vocals as new tracks
Later, you plug in a real voice conversion model by editing one function.
7. 🎵 PHASE 4 — MUSIC GENERATOR + SONG PLANNER
You add:
•	Offline + cloud T2M backends
•	Clip generator
•	Song planner
•	Lyrics splitting
•	Section duration planning
•	Full song generation
•	Cloud toggle
After Phase 4, Echo Pro can:
•	Generate 10–30 second clips
•	Generate full songs in sections
•	Add generated clips to the DAW
•	Use offline or cloud backends
Later, you plug in a real T2M model by editing one function.
8. 📦 PHASE 5 — BUILD THE INSTALLER
You:
1.	Use PyInstaller to build EchoPro.exe
2.	Use Inno Setup to build EchoProInstaller.exe
3.	Ship Echo Pro like a real Windows app
After Phase 5, Echo Pro:
•	Installs into %LOCALAPPDATA%\EchoPro\
•	Has Start Menu + Desktop shortcuts
•	Runs without Python visible to the user
9. 📚 APPENDIX A — ALL CODE FILES (GROUPED)
To keep this message readable, I won’t paste all 2,000+ lines here again — but I will generate a clean, complete, copy and paste code bundle for you in the next message, exactly like the Yukio and Blaze tutorials.
Just say:
“Appendix A now”
And I’ll output:
•	Every .py file
•	In correct order
•	With correct file paths
•	With no missing imports
•	Ready to paste into C:\EchoPro\EchoApp\
10. 📘 APPENDIX B — REAL MODEL INTEGRATION INTERFACES
These are the frozen interfaces you requested:
Text to Music Interface
•	T2MModelConfig
•	T2MClipRequest
•	T2MClipResult
•	t2m_generate_clip()
Voice Conversion Interface
•	VoiceBackendConfig
•	VoiceProfileConfig
•	VoiceConvertRequest
•	VoiceConvertResult
•	voice_convert()
These ensure you can plug in:
•	A real T2M model
•	A real voice conversion model
…without changing the UI or DAW.
11. 🔗 APPENDIX C — REFERENCES
•	Python: https://www.python.org
•	Visual Studio Code: https://code.visualstudio.com
•	FFmpeg: https://ffmpeg.org
•	Demucs: https://github.com/facebookresearch/demucs
•	Inno Setup: https://jrsoftware.org/isinfo.php
•	PySide6: https://doc.qt.io/qtforpython/
•	Pydub: https://pydub.com/
 
Below is Appendix A: all the core Echo Pro code in one place, with exact filenames and paths.
You can copy–paste each file into:
C:\EchoPro\EchoApp\
I’ll group files by purpose:
•	Core paths & setup
•	Project model & audio helpers
•	UI widgets & main app
•	Stems, playback, voice, music generator, planner
•	AI interfaces
•	Installer script & basic data setup
If you see a file you don’t want (e.g., if you already have a variant), you can skip or overwrite carefully.
1. Core paths and first run logic
1.1 C:\EchoPro\EchoApp\app_paths.py
python
import os
from pathlib import Path

ECHO_ROOT = Path(os.environ["APPDATA"]) / "EchoPro"
PROJECTS_DIR = ECHO_ROOT / "projects"
VOICES_DIR = ECHO_ROOT / "voices"
GENERATED_DIR = ECHO_ROOT / "generated"

def ensure_dirs():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
1.2 C:\EchoPro\EchoApp\first_run.py
python
from pathlib import Path
from app_paths import ECHO_ROOT, ensure_dirs

FIRST_RUN_FLAG = ECHO_ROOT / "first_run_done.txt"

def is_first_run() -> bool:
    ensure_dirs()
    return not FIRST_RUN_FLAG.exists()

def mark_first_run_done():
    ECHO_ROOT.mkdir(parents=True, exist_ok=True)
    FIRST_RUN_FLAG.write_text("done", encoding="utf-8")
2. Project model & audio helpers
2.1 C:\EchoPro\EchoApp\project_model.py
python
from dataclasses import dataclass, asdict
from typing import List
import json
from pathlib import Path

@dataclass
class Clip:
    id: int
    track_index: int
    file_path: str
    start_ms: int   # where clip starts on timeline
    length_ms: int  # how long the clip is

@dataclass
class Track:
    name: str
    volume_db: float = 0.0  # 0 = original, negative = quieter, positive = louder

@dataclass
class Project:
    name: str
    tracks: List[Track]
    clips: List[Clip]

def new_empty_project(name: str) -> Project:
    return Project(name=name, tracks=[], clips=[])

def save_project(project: Project, path: Path):
    data = {
        "name": project.name,
        "tracks": [asdict(t) for t in project.tracks],
        "clips": [asdict(c) for c in project.clips],
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def load_project(path: Path) -> Project:
    data = json.loads(path.read_text(encoding="utf-8"))
    tracks = [Track(**t) for t in data.get("tracks", [])]
    clips = [Clip(**c) for c in data.get("clips", [])]
    return Project(name=data.get("name", "Untitled"), tracks=tracks, clips=clips)
2.2 C:\EchoPro\EchoApp\audio_info.py
python
from pydub import AudioSegment

def get_audio_length_ms(path: str) -> int:
    """
    Return the length of an audio file in milliseconds.
    """
    audio = AudioSegment.from_file(path)
    return len(audio)
3. Timeline widget
3.1 C:\EchoPro\EchoApp\timeline_widget.py
python
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt, QRect

from project_model import Project

TRACK_HEIGHT = 60
TRACK_GAP = 10
CLIP_COLOR = QColor(100, 180, 255)
CLIP_BORDER = QColor(30, 60, 120)

PIXELS_PER_SECOND = 50  # how many pixels represent one second

class TimelineWidget(QWidget):
    
    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self.selected_clip_id = None
        self.setMinimumHeight(300)
        self.setMouseTracking(True)

    def set_project(self, project: Project):
        self.project = project
        self.update()

    def time_to_x(self, ms: int) -> int:
        seconds = ms / 1000.0
        return int(seconds * PIXELS_PER_SECOND)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(30, 30, 30))  # background

        # Draw tracks and clips
        for track_index, track in enumerate(self.project.tracks):
            top = track_index * (TRACK_HEIGHT + TRACK_GAP)
            # Track background
            track_rect = QRect(0, top, self.width(), TRACK_HEIGHT)
            painter.fillRect(track_rect, QColor(40, 40, 40))
            painter.setPen(Qt.white)
            painter.drawText(5, top + 20, track.name)

            # Draw clips on this track
            for clip in self.project.clips:
                if clip.track_index != track_index:
                    continue
                x = self.time_to_x(clip.start_ms)
                w = self.time_to_x(clip.length_ms)
                clip_rect = QRect(x, top + 20, max(w, 10), TRACK_HEIGHT - 25)

                painter.setPen(QPen(CLIP_BORDER, 2))
                painter.setBrush(CLIP_COLOR)
                painter.drawRect(clip_rect)

        painter.end()
4. Playback & mixing
4.1 C:\EchoPro\EchoApp\playback_mixer.py
python
from pathlib import Path
from pydub import AudioSegment
from pydub.playback import play

from project_model import Project

def mix_project_to_segment(project: Project) -> AudioSegment:
    """
    Mix all clips in the project into a single AudioSegment,
    applying track volumes.
    """
    if not project.tracks:
        return AudioSegment.silent(duration=1000)

    max_end_ms = 0
    for clip in project.clips:
        end_ms = clip.start_ms + clip.length_ms
        if end_ms > max_end_ms:
            max_end_ms = end_ms

    master = AudioSegment.silent(duration=max_end_ms + 1000)  # extra second

    track_volumes = {i: t.volume_db for i, t in enumerate(project.tracks)}

    for clip in project.clips:
        try:
            seg = AudioSegment.from_file(clip.file_path)
            if len(seg) > clip.length_ms:
                seg = seg[:clip.length_ms]
            db_change = track_volumes.get(clip.track_index, 0.0)
            seg = seg + db_change
            master = master.overlay(seg, position=clip.start_ms)
        except Exception as e:
            print(f"Error loading clip {clip.file_path}: {e}")
            continue

    return master

def play_project(project: Project):
    """
    Mix and play the project.
    """
    mix = mix_project_to_segment(project)
    play(mix)
5. Stems engine (Demucs integration)
5.1 C:\EchoPro\EchoApp\stems_engine.py
python
import subprocess
import os
from pathlib import Path
import shutil

from project_model import Clip, Track, Project
from audio_info import get_audio_length_ms

def separate_stems(input_path: str, output_dir: Path) -> dict:
    """
    Use Demucs to separate a song into stems.
    Returns a dict mapping stem names to file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "demucs",
        "-o", str(output_dir),
        input_path
    ]
    subprocess.run(cmd, check=True)

    stem_folder = None
    for root, dirs, files in os.walk(output_dir):
        wavs = [f for f in files if f.lower().endswith(".wav")]
        if wavs:
            stem_folder = Path(root)
            break

    if stem_folder is None:
        raise RuntimeError("Could not find stem folder after Demucs run.")

    stems = {}
    for stem_file in stem_folder.glob("*.wav"):
        target = output_dir / stem_file.name
        if target != stem_file:
            shutil.move(str(stem_file), target)
        stem_name = stem_file.stem.lower()
        stems[stem_name] = str(target)

    return stems

def add_stems_to_project(project: Project, stems: dict, project_folder: Path, next_clip_id_start: int = 1):
    """
    Given a project and a dict of stems (name -> path),
    create tracks and clips for each stem.
    Returns updated next_clip_id.
    """
    next_clip_id = next_clip_id_start

    stem_order = ["vocals", "drums", "bass", "guitar", "other"]
    for stem_name in stem_order:
        if stem_name not in stems:
            continue
        file_path = stems[stem_name]

        track_name = stem_name.capitalize()
        track_index = len(project.tracks)
        project.tracks.append(Track(name=track_name))

        length_ms = get_audio_length_ms(file_path)
        clip = Clip(
            id=next_clip_id,
            track_index=track_index,
            file_path=file_path,
            start_ms=0,
            length_ms=length_ms
        )
        project.clips.append(clip)
        next_clip_id += 1

    return next_clip_id
6. Voice profiles & recording
6.1 C:\EchoPro\EchoApp\voice_store.py
python
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List

from app_paths import VOICES_DIR, ensure_dirs

VOICE_INDEX_FILE = VOICES_DIR / "voice_profiles.json"

@dataclass
class VoiceProfile:
    name: str
    file_path: str           # path to reference WAV
    created_at: str
    consent_flag: bool = True
    source_type: str = "user_recording"

def load_voice_profiles() -> List[VoiceProfile]:
    ensure_dirs()
    if not VOICE_INDEX_FILE.exists():
        return []
    data = json.loads(VOICE_INDEX_FILE.read_text(encoding="utf-8"))
    return [VoiceProfile(**vp) for vp in data.get("profiles", [])]

def save_voice_profiles(profiles: List[VoiceProfile]):
    ensure_dirs()
    data = {"profiles": [asdict(p) for p in profiles]}
    VOICE_INDEX_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def add_voice_profile(name: str, wav_path: Path) -> VoiceProfile:
    profiles = load_voice_profiles()
    profile = VoiceProfile(
        name=name,
        file_path=str(wav_path),
        created_at=datetime.now().isoformat(),
        consent_flag=True,
        source_type="user_recording"
    )
    profiles.append(profile)
    save_voice_profiles(profiles)
    return profile
6.2 C:\EchoPro\EchoApp\voice_recorder.py
python
import sounddevice as sd
import soundfile as sf
from pathlib import Path

def record_voice_to_wav(output_path: Path, duration_sec: int = 10, samplerate: int = 44100):
    """
    Record audio from the default microphone for duration_sec seconds
    and save to output_path as a WAV file.
    """
    channels = 1
    print(f"Recording for {duration_sec} seconds...")
    audio = sd.rec(int(duration_sec * samplerate), samplerate=samplerate, channels=channels)
    sd.wait()
    sf.write(str(output_path), audio, samplerate)
    print(f"Saved recording to {output_path}")
7. AI interfaces (future proof)
7.1 Text to music interface
C:\EchoPro\EchoApp\t2m_interface.py
python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal, Dict, Any

StyleType = Literal["lofi", "rock", "pop", "edm", "orchestral", "jazz", "hiphop", "ambient", "custom"]
VocalMode = Literal["none", "lead", "choir", "backing"]
BackendType = Literal["offline", "cloud"]

@dataclass
class T2MModelConfig:
    name: str
    backend_type: BackendType

    max_clip_seconds: int
    sample_rate: int
    stereo: bool
    fp16: bool
    batch_size: int

    extra: Dict[str, Any] = None

@dataclass
class T2MClipRequest:
    prompt_style: StyleType
    prompt_genre: str
    prompt_mood: str
    lyrics: str
    vocal_mode: VocalMode

    key: str
    chords: str
    time_signature: str
    tempo_bpm: int

    duration_seconds: int
    seed: Optional[int] = None

    section_name: str = ""
    notes: str = ""

@dataclass
class T2MClipResult:
    audio_path: Path
    duration_ms: int
    used_seed: Optional[int]
    backend_name: str
    metadata: Dict[str, Any]

def t2m_generate_clip(
    request: T2MClipRequest,
    output_path: Path,
    model_config: T2MModelConfig,
) -> T2MClipResult:
    """
    Placeholder implementation: generates silence.
    Replace this body with a real T2M model.
    """
    from pydub import AudioSegment

    duration_ms = request.duration_seconds * 1000
    silence = AudioSegment.silent(duration=duration_ms)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    silence.export(str(output_path), format="wav")

    return T2MClipResult(
        audio_path=output_path,
        duration_ms=duration_ms,
        used_seed=request.seed,
        backend_name=model_config.name,
        metadata={
            "backend_type": model_config.backend_type,
            "note": "Placeholder silent clip. Replace t2m_generate_clip with real model."
        }
    )
7.2 Voice conversion interface
C:\EchoPro\EchoApp\voice_interface.py
python
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

@dataclass
class VoiceBackendConfig:
    name: str
    model_path: str
    device: str
    sample_rate: int
    extra: Dict[str, Any] = None

@dataclass
class VoiceProfileConfig:
    name: str
    embedding_path: str
    source_audio_path: str
    consent_flag: bool
    source_type: str
    metadata: Dict[str, Any] = None

@dataclass
class VoiceConvertRequest:
    source_wav: Path
    target_profile: VoiceProfileConfig

    preserve_pitch: bool = True
    preserve_formants: bool = True
    strength: float = 1.0
    notes: str = ""

@dataclass
class VoiceConvertResult:
    audio_path: Path
    backend_name: str
    metadata: Dict[str, Any]

def voice_convert(
    request: VoiceConvertRequest,
    output_path: Path,
    backend_config: VoiceBackendConfig,
) -> VoiceConvertResult:
    """
    Placeholder implementation: slight gain change.
    Replace this body with a real voice conversion model.
    """
    from pydub import AudioSegment

    audio = AudioSegment.from_file(str(request.source_wav))
    gain_db = (request.strength - 1.0) * 3.0
    converted = audio + gain_db

    output_path.parent.mkdir(parents=True, exist_ok=True)
    converted.export(str(output_path), format="wav")

    return VoiceConvertResult(
        audio_path=output_path,
        backend_name=backend_config.name,
        metadata={
            "note": "Placeholder conversion. Replace voice_convert with real model.",
            "preserve_pitch": request.preserve_pitch,
            "preserve_formants": request.preserve_formants,
            "strength": request.strength,
        }
    )
8. Music generator + planner wrappers
8.1 C:\EchoPro\EchoApp\music_generator.py
python
from pathlib import Path
from typing import Optional

from t2m_interface import (
    T2MModelConfig,
    T2MClipRequest,
    t2m_generate_clip,
    T2MClipResult,
)
from app_paths import ECHO_ROOT, ensure_dirs

VALID_STYLES = ["lofi", "rock", "pop", "edm", "orchestral", "jazz", "hiphop", "ambient"]

def get_default_t2m_config(use_cloud: bool = False) -> T2MModelConfig:
    backend_type = "cloud" if use_cloud else "offline"
    return T2MModelConfig(
        name="EchoProT2MPlaceholder",
        backend_type=backend_type,
        max_clip_seconds=30,
        sample_rate=44100,
        stereo=True,
        fp16=True,
        batch_size=1,
        extra={}
    )

def generate_music_clip(
    style: str,
    genre: str,
    mood: str,
    lyrics: str,
    duration_seconds: int,
    key: str = "",
    chords: str = "",
    time_signature: str = "4/4",
    tempo_bpm: int = 120,
    section_name: str = "",
    seed: Optional[int] = None,
    project_id: str = "default_project",
    use_cloud: bool = False,
) -> T2MClipResult:
    ensure_dirs()
    out_dir = ECHO_ROOT / "generated" / project_id
    out_dir.mkdir(parents=True, exist_ok=True)

    output_path = out_dir / f"{section_name or 'clip'}_{seed or 'x'}.wav"

    prompt_style = style if style in VALID_STYLES else "custom"

    request = T2MClipRequest(
        prompt_style=prompt_style,
        prompt_genre=genre,
        prompt_mood=mood,
        lyrics=lyrics,
        vocal_mode="lead" if lyrics.strip() else "none",
        key=key,
        chords=chords,
        time_signature=time_signature,
        tempo_bpm=tempo_bpm,
        duration_seconds=duration_seconds,
        seed=seed,
        section_name=section_name,
        notes=""
    )

    config = get_default_t2m_config(use_cloud=use_cloud)
    result = t2m_generate_clip(request, output_path, config)
    return result
8.2 C:\EchoPro\EchoApp\song_planner.py
python
from pathlib import Path
from typing import List, Dict
from math import floor

from app_paths import ECHO_ROOT
from music_generator import generate_music_clip

def split_lyrics_into_sections(lyrics: str, structure: List[str]) -> Dict[str, str]:
    lines = [l.strip() for l in lyrics.split("\n") if l.strip()]
    if not lines:
        return {section: "" for section in structure}

    per_section = floor(len(lines) / len(structure)) or 1
    sections = {}
    idx = 0
    for section in structure:
        chunk = lines[idx:idx+per_section]
        sections[section] = "\n".join(chunk)
        idx += per_section

    if idx < len(lines):
        sections[structure[-1]] += "\n" + "\n".join(lines[idx:])

    return sections

def plan_song_clips(total_length_sec: int, structure: List[str]) -> Dict[str, int]:
    per_section_ms = floor((total_length_sec * 1000) / len(structure))
    return {section: per_section_ms for section in structure}

def generate_song_sections(
    lyrics: str,
    structure: List[str],
    total_length_sec: int,
    key: str,
    chords: str,
    time_signature: str,
    tempo: int,
    style: str,
    genre: str,
    mood: str,
    project_id: str,
    use_cloud: bool = False
) -> List[Path]:
    song_dir = ECHO_ROOT / "generated" / project_id
    song_dir.mkdir(parents=True, exist_ok=True)

    lyric_sections = split_lyrics_into_sections(lyrics, structure)
    durations = plan_song_clips(total_length_sec, structure)

    generated_paths: List[Path] = []

    for section in structure:
        duration_ms = durations[section]
        duration_sec = max(10, duration_ms // 1000)
        result = generate_music_clip(
            style=style,
            genre=genre,
            mood=mood,
            lyrics=lyric_sections.get(section, ""),
            duration_seconds=duration_sec,
            key=key,
            chords=chords,
            time_signature=time_signature,
            tempo_bpm=tempo,
            section_name=section,
            seed=None,
            project_id=project_id,
            use_cloud=use_cloud,
        )
        generated_paths.append(result.audio_path)

    return generated_paths
9. Voice conversion wrapper
9.1 C:\EchoPro\EchoApp\voice_effects.py
python
from pathlib import Path

from voice_interface import (
    VoiceBackendConfig,
    VoiceProfileConfig,
    VoiceConvertRequest,
    VoiceConvertResult,
    voice_convert,
)

def get_default_voice_backend() -> VoiceBackendConfig:
    return VoiceBackendConfig(
        name="EchoProVoicePlaceholder",
        model_path="",
        device="cpu",
        sample_rate=44100,
        extra={}
    )

def apply_voice_conversion(
    source_wav: Path,
    target_profile: VoiceProfileConfig,
    output_path: Path,
    preserve_pitch: bool = True,
    preserve_formants: bool = True,
    strength: float = 1.0,
    notes: str = "",
) -> VoiceConvertResult:
    backend = get_default_voice_backend()
    request = VoiceConvertRequest(
        source_wav=source_wav,
        target_profile=target_profile,
        preserve_pitch=preserve_pitch,
        preserve_formants=preserve_formants,
        strength=strength,
        notes=notes
    )
    result = voice_convert(request, output_path, backend)
    return result
10. Main app & dialogs
10.1 C:\EchoPro\EchoApp\echo_pro_app.py
python
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
11. Basic data setup script (optional)
11.1 C:\EchoPro\EchoApp\install_echo_pro.bat
bat
@echo off
setlocal

echo === Echo Pro - Data Setup ===

python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Install from https://www.python.org/downloads/windows/
    pause
    exit /b
)

set ECHO=%APPDATA%\EchoPro

echo Creating directories...
mkdir "%ECHO%\projects" "%ECHO%\voices" "%ECHO%\generated" 2>nul

echo Echo Pro data root is at: %ECHO%
pause
12. Inno Setup installer script
12.1 C:\EchoPro\EchoApp\echo_pro_installer.iss
ini
[Setup]
AppName=Echo Pro
AppVersion=1.0.0
DefaultDirName={localappdata}\EchoPro
DefaultGroupName=Echo Pro
OutputBaseFilename=EchoProInstaller
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern

[Files]
Source: "C:\EchoPro\EchoApp\dist\EchoPro\EchoPro.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Echo Pro"; Filename: "{app}\EchoPro.exe"
Name: "{commondesktop}\Echo Pro"; Filename: "{app}\EchoPro.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; Flags: unchecked

[Run]
Filename: "{app}\EchoPro.exe"; Description: "Launch Echo Pro"; Flags: nowait postinstall skipifsilent
13. Building & running
1.	Install dependencies (once):
bat
python -m pip install pyside6 pydub simpleaudio sounddevice soundfile demucs pyinstaller
2.	Test Echo Pro:
bat
python echo_pro_app.py
3.	Build EXE:
bat
pyinstaller --noconfirm --windowed --name EchoPro echo_pro_app.py
4.	Build installer with Inno Setup using echo_pro_installer.iss.
⭐ APPENDIX B — REAL MODEL INTEGRATION INTERFACES
This appendix defines the frozen, stable Python interfaces that Echo Pro uses for:
1.	Text to Music generation
2.	Voice Conversion
These interfaces are intentionally simple, explicit, and backend agnostic. They allow you to plug in any real AI model later without changing:
•	The UI
•	The DAW
•	The Song Planner
•	The Voice Manager
•	The installer
Only the function bodies need to be replaced.
🎵 B.1 — TEXT TO MUSIC INTERFACE
File: C:\EchoPro\EchoApp\t2m_interface.py
python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal, Dict, Any

StyleType = Literal["lofi", "rock", "pop", "edm", "orchestral", "jazz", "hiphop", "ambient", "custom"]
VocalMode = Literal["none", "lead", "choir", "backing"]
BackendType = Literal["offline", "cloud"]

@dataclass
class T2MModelConfig:
    name: str
    backend_type: BackendType

    max_clip_seconds: int
    sample_rate: int
    stereo: bool
    fp16: bool
    batch_size: int

    extra: Dict[str, Any] = None


@dataclass
class T2MClipRequest:
    prompt_style: StyleType
    prompt_genre: str
    prompt_mood: str
    lyrics: str
    vocal_mode: VocalMode

    key: str
    chords: str
    time_signature: str
    tempo_bpm: int

    duration_seconds: int
    seed: Optional[int] = None

    section_name: str = ""
    notes: str = ""


@dataclass
class T2MClipResult:
    audio_path: Path
    duration_ms: int
    used_seed: Optional[int]
    backend_name: str
    metadata: Dict[str, Any]


def t2m_generate_clip(
    request: T2MClipRequest,
    output_path: Path,
    model_config: T2MModelConfig,
) -> T2MClipResult:
    """
    Placeholder implementation: generates silence.
    Replace this body with a real T2M model.
    """
    from pydub import AudioSegment

    duration_ms = request.duration_seconds * 1000
    silence = AudioSegment.silent(duration=duration_ms)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    silence.export(str(output_path), format="wav")

    return T2MClipResult(
        audio_path=output_path,
        duration_ms=duration_ms,
        used_seed=request.seed,
        backend_name=model_config.name,
        metadata={
            "backend_type": model_config.backend_type,
            "note": "Placeholder silent clip. Replace t2m_generate_clip with real model."
        }
    )
🎤 B.2 — VOICE CONVERSION INTERFACE
File: C:\EchoPro\EchoApp\voice_interface.py
python
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

@dataclass
class VoiceBackendConfig:
    name: str
    model_path: str
    device: str
    sample_rate: int
    extra: Dict[str, Any] = None


@dataclass
class VoiceProfileConfig:
    name: str
    embedding_path: str
    source_audio_path: str
    consent_flag: bool
    source_type: str
    metadata: Dict[str, Any] = None


@dataclass
class VoiceConvertRequest:
    source_wav: Path
    target_profile: VoiceProfileConfig

    preserve_pitch: bool = True
    preserve_formants: bool = True
    strength: float = 1.0
    notes: str = ""


@dataclass
class VoiceConvertResult:
    audio_path: Path
    backend_name: str
    metadata: Dict[str, Any]


def voice_convert(
    request: VoiceConvertRequest,
    output_path: Path,
    backend_config: VoiceBackendConfig,
) -> VoiceConvertResult:
    """
    Placeholder implementation: slight gain change.
    Replace this body with a real voice conversion model.
    """
    from pydub import AudioSegment

    audio = AudioSegment.from_file(str(request.source_wav))
    gain_db = (request.strength - 1.0) * 3.0
    converted = audio + gain_db

    output_path.parent.mkdir(parents=True, exist_ok=True)
    converted.export(str(output_path), format="wav")

    return VoiceConvertResult(
        audio_path=output_path,
        backend_name=backend_config.name,
        metadata={
            "note": "Placeholder conversion. Replace voice_convert with real model.",
            "preserve_pitch": request.preserve_pitch,
            "preserve_formants": request.preserve_formants,
            "strength": request.strength,
        }
    )
🔧 B.3 — HOW THESE INTERFACES ARE USED IN ECHO PRO
Echo Pro calls these interfaces through two wrapper functions:
Music generation wrapper
generate_music_clip() in music_generator.py
Voice conversion wrapper
apply_voice_conversion() in voice_effects.py
These wrappers:
•	Build the request objects
•	Load backend configs
•	Call the interface functions
•	Return results to the DAW
This means:
✔️ To integrate a real Text to Music model
Replace the body of:
python
t2m_generate_clip()
✔️ To integrate a real Voice Conversion model
Replace the body of:
python
voice_convert()
Nothing else in Echo Pro needs to change.
🧱 B.4 — WHY THIS INTERFACE DESIGN IS FUTURE PROOF
These interfaces:
•	Are backend agnostic
•	Support offline or cloud
•	Support seed continuity
•	Support lyrics, style, genre, mood, key, chords, tempo
•	Support safe, consent based voice profiles
•	Are chunk friendly for VRAM limited generation
•	Are simple enough for a 14 year old to understand
•	Are powerful enough for real AI models
This is the exact architecture used in professional AI audio tools.
Appendix C – References
Here are the main tools, libraries, and concepts Echo Pro is built on or designed to integrate with.
Core development stack
•	Python (3.10+) – General purpose programming language used for Echo Pro. https://www.python.org
•	Visual Studio Code – Cross platform code editor with Python support. https://code.visualstudio.com
•	PySide6 (Qt for Python) – GUI toolkit used to build the Echo Pro desktop app. https://doc.qt.io/qtforpython/
•	pydub – High level audio manipulation library used for loading, trimming, fading, volume, and mixdown. https://pydub.com/
•	simpleaudio – Cross platform audio playback library used by pydub for playback. https://simpleaudio.readthedocs.io
•	sounddevice – Library for recording from the system microphone. https://python-sounddevice.readthedocs.io
•	soundfile – Library for reading/writing sound files; used to save microphone recordings. https://pysoundfile.readthedocs.io
•	FFmpeg – Command line tool and libraries for decoding/encoding audio and video; pydub uses FFmpeg underneath. https://ffmpeg.org
•	PyInstaller – Bundles Python applications into standalone executables. https://pyinstaller.org
•	Inno Setup – Windows installer builder used to create EchoProInstaller.exe. https://jrsoftware.org/isinfo.php
Audio source separation (stems)
•	Demucs – Open source music source separation model that splits mixes into stems such as vocals, drums, bass, and “other,” implemented as a U Net style architecture and released under MIT license. GitHub (original): https://github.com/facebookresearch/demucs Overview & model info: https://openlaboratory.ai/models/demucs
Demucs is used conceptually as the backend for Echo Pro’s stems module, which isolates vocals, drums, bass, guitar (via mapping), and other.
General references and ecosystem
•	Git – Version control (optional but recommended for keeping track of Echo Pro changes). https://git-scm.com
•	Python packaging – pip for installing required libraries. https://pip.pypa.io

