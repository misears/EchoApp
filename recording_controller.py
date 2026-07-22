"""
Echo Pro Recording Controller
Coordinates the audio engine, metronome, recording session, and undo history.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import numpy as np
import sounddevice as sd

from audio_engine import AudioEngine
from metronome import Metronome, MetronomeConfig
from recording_session import RecordingSession, RecordingPreset
from undo_manager import UndoManager


@dataclass
class RecordingStatus:
    is_armed: bool = False
    is_recording: bool = False
    count_in_active: bool = False
    active_track_ids: List[int] = field(default_factory=list)
    last_error: str = ""
    current_tempo_bpm: int = 120
    time_signature: str = "4/4"


class RecordingController:
    """High-level recording transport and take management."""

    def __init__(self, session_id: str, project_name: str, sample_rate: int = 44100, buffer_size: int = 256):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.engine = AudioEngine(sample_rate=sample_rate, buffer_size=buffer_size)
        self.session = RecordingSession(session_id, project_name)
        self.session.initialize_tracks(len(self.engine.tracks))
        self.metronome = Metronome(MetronomeConfig(sample_rate=sample_rate))
        self.undo_manager = UndoManager(max_levels=self.session.max_undo_levels)
        self.status = RecordingStatus()
        self.armed_tracks: Set[int] = set()
        self.active_take_ids: Dict[int, int] = {}
        self.stream: Optional[sd.Stream] = None

    def configure_preset(self, preset: RecordingPreset) -> None:
        self.session.set_preset(preset)
        self.metronome.set_tempo(preset.metronome_bpm or self.status.current_tempo_bpm)
        self.metronome.config.count_in_bars = max(0, preset.auto_punch_start_bars)
        self.status.current_tempo_bpm = self.metronome.config.bpm
        self.status.time_signature = f"{self.metronome.config.time_signature[0]}/{self.metronome.config.time_signature[1]}"

    def arm_track(self, track_id: int) -> bool:
        if self.engine.get_track(track_id) is None:
            self.status.last_error = f"Track {track_id} does not exist"
            return False
        self.armed_tracks.add(track_id)
        self.status.active_track_ids = sorted(self.armed_tracks)
        self.status.is_armed = True
        return True

    def disarm_track(self, track_id: int) -> None:
        self.armed_tracks.discard(track_id)
        self.status.active_track_ids = sorted(self.armed_tracks)
        self.status.is_armed = bool(self.armed_tracks)

    def arm_all_tracks(self) -> None:
        self.armed_tracks = {track.track_id for track in self.engine.tracks}
        self.status.active_track_ids = sorted(self.armed_tracks)
        self.status.is_armed = True

    def clear_armed_tracks(self) -> None:
        self.armed_tracks.clear()
        self.status.active_track_ids = []
        self.status.is_armed = False

    def set_tempo(self, bpm: int) -> None:
        self.metronome.set_tempo(bpm)
        self.status.current_tempo_bpm = self.metronome.config.bpm

    def set_time_signature(self, numerator: int, denominator: int) -> None:
        self.metronome.set_time_signature(numerator, denominator)
        self.status.time_signature = f"{numerator}/{denominator}"

    def start_count_in(self, bars: Optional[int] = None) -> np.ndarray:
        self.status.count_in_active = True
        count_in = self.metronome.count_in_block(bars)
        self.status.count_in_active = False
        return count_in

    def start_recording(self) -> bool:
        if not self.armed_tracks:
            self.status.last_error = "No tracks armed for recording"
            return False

        self.engine.start_recording()
        self.metronome.start()
        self.status.is_recording = True
        self.status.last_error = ""

        for track_id in self.armed_tracks:
            take = self.session.start_new_take(track_id)
            self.active_take_ids[track_id] = take.take_number

        return True

    def start_stream(self, input_device: Optional[int] = None, output_device: Optional[int] = None) -> bool:
        """Open a live audio stream and route callbacks through the controller."""
        if self.stream is not None:
            return True

        try:
            self.stream = sd.Stream(
                device=(input_device, output_device),
                samplerate=self.sample_rate,
                blocksize=self.buffer_size,
                channels=2,
                dtype=np.float32,
                callback=self._audio_callback,
                latency='low',
            )
            self.stream.start()
            return True
        except Exception as exc:
            self.status.last_error = str(exc)
            self.stream = None
            return False

    def stop_stream(self) -> None:
        """Stop the live audio stream if it is running."""
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def _audio_callback(self, indata, outdata, frames, time_info, status):
        if status:
            self.status.last_error = str(status)

        input_audio = indata.T.copy()
        click = self.process_recording_block(input_audio)

        if self.status.is_recording:
            output = input_audio + click
        else:
            output = click

        if output.shape[0] < 2:
            output = np.vstack([output, output])

        outdata[:] = output.T[:frames]

    def stop_recording(self, duration_seconds: float = 0.0, level_stats: Optional[Dict[int, Dict[str, float]]] = None) -> None:
        self.engine.stop_recording()
        self.metronome.stop()
        self.status.is_recording = False

        level_stats = level_stats or {}
        for track_id in list(self.active_take_ids.keys()):
            take_stats = level_stats.get(track_id, {"rms": -80.0, "peak": -80.0, "clipping": 0.0})
            self.session.finish_take(track_id, duration_seconds, take_stats)
            self.active_take_ids.pop(track_id, None)

        self.session.save_session_metadata()
        self.stop_stream()

    def process_recording_block(self, input_audio: np.ndarray) -> np.ndarray:
        """Process one audio callback block and return the metronome monitor mix."""
        if input_audio.ndim != 2:
            raise ValueError("input_audio must be a 2D array shaped (channels, frames)")

        if self.status.is_recording:
            for track_id in self.armed_tracks:
                track = self.engine.get_track(track_id)
                if track is not None:
                    track.record(input_audio)

        click = self.metronome.render_block(input_audio.shape[1]) if self.metronome.is_running else np.zeros_like(input_audio)
        return click

    def get_status_snapshot(self) -> RecordingStatus:
        snapshot = RecordingStatus(
            is_armed=self.status.is_armed,
            is_recording=self.status.is_recording,
            count_in_active=self.status.count_in_active,
            active_track_ids=list(self.status.active_track_ids),
            last_error=self.status.last_error,
            current_tempo_bpm=self.status.current_tempo_bpm,
            time_signature=self.status.time_signature,
        )
        return snapshot

    def undo_last_take(self):
        return self.session.undo_last_take()

    def redo_last_take(self):
        return self.session.redo_last_take()

    def get_meter_levels(self) -> Dict[int, Dict[str, float]]:
        levels: Dict[int, Dict[str, float]] = {}
        for track in self.engine.tracks:
            levels[track.track_id] = {
                "current_db": track.current_level_db,
                "peak_db": track.peak_level_db,
                "clipping": 1.0 if track.clipping_detected else 0.0,
            }
        return levels
