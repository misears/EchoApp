"""
Echo Pro Recording Controller
Coordinates the audio engine, metronome, recording session, and undo history.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from pathlib import Path
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

from app_paths import ECHO_ROOT

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
    punch_enabled: bool = False
    loop_enabled: bool = False
    loop_cycle_index: int = 0
    pre_roll_bars: float = 0.0
    post_roll_bars: float = 0.0
    last_auto_stop_sample: int = 0


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
        self.active_take_start_samples: Dict[int, int] = {}
        self.stream: Optional[sd.Stream] = None
        self._pending_count_in: Optional[np.ndarray] = None
        self._count_in_cursor = 0
        self.audition_active = False
        self.audition_looping = False
        self.punch_enabled = False
        self.punch_in_samples = 0
        self.punch_out_samples: Optional[int] = None
        self.pre_roll_samples = 0
        self.post_roll_samples = 0
        self.loop_enabled = False
        self.loop_start_samples = 0
        self.loop_end_samples: Optional[int] = None
        self.loop_cycle_index = 0
        self._transport_sample_cursor = 0
        self._auto_stop_event_pending = False
        self._loop_next_start_cursor: Optional[int] = None
        self._loop_next_end_cursor: Optional[int] = None
        self._punch_start_marker = 0
        self._punch_stop_marker: Optional[int] = None
        self._last_auto_stop_sample = 0
        self._transport_diagnostics: Dict[str, int] = {
            "loop_cycles_completed": 0,
            "punch_start_hits": 0,
            "punch_stop_hits": 0,
            "auto_stop_events": 0,
            "last_start_sample": 0,
            "last_stop_sample": 0,
            "last_auto_stop_sample": 0,
        }
        self._transport_last_error = ""
        self.auto_disarm_after_boundary = False
        self._transport_action_debounce_sec = 0.2
        self._last_start_action_ts = 0.0
        self._last_stop_action_ts = 0.0

    def _beats_per_bar(self) -> int:
        return max(1, int(self.metronome.config.time_signature[0]))

    def _seconds_per_beat(self) -> float:
        return 60.0 / float(max(1, self.metronome.config.bpm))

    def samples_to_bars(self, samples: int) -> float:
        seconds = float(max(0, int(samples))) / float(self.sample_rate)
        return seconds / (self._beats_per_bar() * self._seconds_per_beat())

    def bars_to_samples(self, bars: float) -> int:
        seconds = float(max(0.0, float(bars))) * self._beats_per_bar() * self._seconds_per_beat()
        return int(round(seconds * self.sample_rate))

    def configure_preset(self, preset: RecordingPreset) -> None:
        self.session.set_preset(preset)
        self.metronome.set_tempo(preset.metronome_bpm or self.status.current_tempo_bpm)
        self.metronome.config.count_in_bars = max(0, preset.auto_punch_start_bars)
        self.auto_disarm_after_boundary = bool(getattr(preset, "auto_disarm_after_boundary", False))
        self.status.current_tempo_bpm = self.metronome.config.bpm
        self.status.time_signature = f"{self.metronome.config.time_signature[0]}/{self.metronome.config.time_signature[1]}"

    def set_auto_disarm_after_boundary(self, enabled: bool) -> None:
        self.auto_disarm_after_boundary = bool(enabled)

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

    def set_count_in_bars(self, bars: int) -> None:
        self.metronome.config.count_in_bars = max(0, bars)

    def set_punch_enabled(self, enabled: bool) -> None:
        self.punch_enabled = bool(enabled)
        self.status.punch_enabled = self.punch_enabled

    def set_pre_post_roll_samples(self, pre_roll_samples: int, post_roll_samples: int) -> bool:
        pre_roll = int(pre_roll_samples)
        post_roll = int(post_roll_samples)
        if pre_roll < 0:
            self.status.last_error = "Pre-roll samples cannot be negative"
            return False
        if post_roll < 0:
            self.status.last_error = "Post-roll samples cannot be negative"
            return False

        self.pre_roll_samples = pre_roll
        self.post_roll_samples = post_roll
        self.status.pre_roll_bars = self.samples_to_bars(self.pre_roll_samples)
        self.status.post_roll_bars = self.samples_to_bars(self.post_roll_samples)
        self.status.last_error = ""
        return True

    def set_pre_post_roll_bars(self, pre_roll_bars: float, post_roll_bars: float) -> bool:
        if pre_roll_bars < 0:
            self.status.last_error = "Pre-roll bars cannot be negative"
            return False
        if post_roll_bars < 0:
            self.status.last_error = "Post-roll bars cannot be negative"
            return False

        pre_roll_samples = self.bars_to_samples(pre_roll_bars)
        post_roll_samples = self.bars_to_samples(post_roll_bars)
        return self.set_pre_post_roll_samples(pre_roll_samples, post_roll_samples)

    def set_punch_range_samples(self, punch_in_samples: int, punch_out_samples: Optional[int] = None) -> bool:
        punch_in = max(0, int(punch_in_samples))
        punch_out = None if punch_out_samples is None else int(punch_out_samples)
        if punch_out is not None and punch_out <= punch_in:
            self.status.last_error = "Punch-out sample must be greater than punch-in sample"
            return False

        self.punch_in_samples = punch_in
        self.punch_out_samples = punch_out
        self.status.last_error = ""
        return True

    def set_punch_range_seconds(self, punch_in_seconds: float, punch_out_seconds: Optional[float] = None) -> bool:
        if punch_in_seconds < 0:
            self.status.last_error = "Punch-in seconds cannot be negative"
            return False
        if punch_out_seconds is not None and punch_out_seconds <= punch_in_seconds:
            self.status.last_error = "Punch-out seconds must be greater than punch-in seconds"
            return False

        punch_in_samples = int(round(float(punch_in_seconds) * self.sample_rate))
        punch_out_samples = None
        if punch_out_seconds is not None:
            punch_out_samples = int(round(float(punch_out_seconds) * self.sample_rate))
        return self.set_punch_range_samples(punch_in_samples, punch_out_samples)

    def set_punch_range_bars(self, punch_in_bars: float, punch_out_bars: Optional[float] = None) -> bool:
        if punch_in_bars < 0:
            self.status.last_error = "Punch-in bars cannot be negative"
            return False
        if punch_out_bars is not None and punch_out_bars <= punch_in_bars:
            self.status.last_error = "Punch-out bars must be greater than punch-in bars"
            return False

        beats_per_bar = self._beats_per_bar()
        seconds_per_beat = self._seconds_per_beat()

        punch_in_seconds = float(punch_in_bars) * beats_per_bar * seconds_per_beat
        punch_out_seconds = None
        if punch_out_bars is not None:
            punch_out_seconds = float(punch_out_bars) * beats_per_bar * seconds_per_beat
        return self.set_punch_range_seconds(punch_in_seconds, punch_out_seconds)

    def set_loop_enabled(self, enabled: bool) -> None:
        self.loop_enabled = bool(enabled)
        self.status.loop_enabled = self.loop_enabled

    def set_loop_range_samples(self, loop_start_samples: int, loop_end_samples: Optional[int]) -> bool:
        loop_start = max(0, int(loop_start_samples))
        if loop_end_samples is None:
            self.status.last_error = "Loop end sample is required"
            return False
        loop_end = int(loop_end_samples)
        if loop_end <= loop_start:
            self.status.last_error = "Loop end sample must be greater than loop start sample"
            return False

        self.loop_start_samples = loop_start
        self.loop_end_samples = loop_end
        self.status.last_error = ""
        return True

    def set_loop_range_seconds(self, loop_start_seconds: float, loop_end_seconds: float) -> bool:
        if loop_start_seconds < 0:
            self.status.last_error = "Loop start seconds cannot be negative"
            return False
        if loop_end_seconds <= loop_start_seconds:
            self.status.last_error = "Loop end seconds must be greater than loop start seconds"
            return False

        loop_start_samples = int(round(float(loop_start_seconds) * self.sample_rate))
        loop_end_samples = int(round(float(loop_end_seconds) * self.sample_rate))
        return self.set_loop_range_samples(loop_start_samples, loop_end_samples)

    def set_loop_range_bars(self, loop_start_bars: float, loop_end_bars: float) -> bool:
        if loop_start_bars < 0:
            self.status.last_error = "Loop start bars cannot be negative"
            return False
        if loop_end_bars <= loop_start_bars:
            self.status.last_error = "Loop end bars must be greater than loop start bars"
            return False

        beats_per_bar = self._beats_per_bar()
        seconds_per_beat = self._seconds_per_beat()
        loop_start_seconds = float(loop_start_bars) * beats_per_bar * seconds_per_beat
        loop_end_seconds = float(loop_end_bars) * beats_per_bar * seconds_per_beat
        return self.set_loop_range_seconds(loop_start_seconds, loop_end_seconds)

    def start_count_in(self, bars: Optional[int] = None) -> np.ndarray:
        self.status.count_in_active = True
        count_in = self.metronome.count_in_block(bars)
        self.status.count_in_active = False
        return count_in

    def _start_new_takes_for_armed_tracks(self) -> None:
        for track_id in self.armed_tracks:
            take = self.session.start_new_take(track_id)
            self.active_take_ids[track_id] = take.take_number
            track = self.engine.get_track(track_id)
            if track is not None:
                self.active_take_start_samples[track_id] = track.recording_buffer.get_current_position()

    def _begin_take_capture(self, start_metronome: bool = True, start_engine: bool = True) -> None:
        if start_engine:
            self.engine.start_recording()
        if start_metronome:
            self.metronome.start()
        self.status.is_recording = True
        self.status.last_error = ""
        self._transport_diagnostics["last_start_sample"] = int(self._transport_sample_cursor)
        self._transport_last_error = ""
        if self.loop_enabled and self.loop_cycle_index == 0:
            self.loop_cycle_index = 1
            self.status.loop_cycle_index = self.loop_cycle_index

        self._start_new_takes_for_armed_tracks()

    def _finalize_active_takes(
        self,
        duration_seconds: float = 0.0,
        level_stats: Optional[Dict[int, Dict[str, float]]] = None,
    ) -> None:
        level_stats = level_stats or {}
        for track_id in list(self.active_take_ids.keys()):
            take_stats = level_stats.get(track_id, {"rms": -80.0, "peak": -80.0, "clipping": 0.0})
            track = self.engine.get_track(track_id)
            start_sample = self.active_take_start_samples.get(track_id, 0)
            end_sample = start_sample
            if track is not None:
                end_sample = track.recording_buffer.get_current_position()

            take_duration = duration_seconds
            if take_duration <= 0.0 and track is not None:
                if end_sample >= start_sample:
                    sample_count = end_sample - start_sample
                else:
                    sample_count = (track.recording_buffer.size - start_sample) + end_sample
                take_duration = sample_count / float(self.sample_rate)

            clip_events = 0
            if track is not None:
                diagnostics = track.get_recording_diagnostics()
                take_stats.setdefault("clip_events", int(diagnostics.get("clip_events", 0)))
                take_stats.setdefault("silence_events", int(diagnostics.get("silence_events", 0)))
                clip_events = int(diagnostics.get("clip_events", 0))

            self.session.finish_take(
                track_id,
                take_duration,
                take_stats,
                start_sample=start_sample,
                end_sample=end_sample,
                clip_events=clip_events,
            )
            self.active_take_ids.pop(track_id, None)
            self.active_take_start_samples.pop(track_id, None)

    def start_recording(self) -> bool:
        now = time.monotonic()
        if now - self._last_start_action_ts < self._transport_action_debounce_sec:
            self.status.last_error = "Start recording ignored due to rapid repeated trigger"
            return False

        if not self.armed_tracks:
            self.status.last_error = "No tracks armed for recording"
            return False

        self.stop_audition()

        if self.punch_enabled and self.loop_enabled:
            self.status.last_error = "Punch and loop modes cannot be enabled at the same time"
            return False

        if self.punch_enabled and self.punch_out_samples is not None and self.punch_out_samples <= self.punch_in_samples:
            self.status.last_error = "Punch-out must be greater than punch-in"
            return False

        if self.loop_enabled:
            if self.loop_end_samples is None:
                self.status.last_error = "Loop mode requires a loop start and loop end"
                return False
            if self.loop_end_samples <= self.loop_start_samples:
                self.status.last_error = "Loop end must be greater than loop start"
                return False

        self._transport_sample_cursor = 0
        self._auto_stop_event_pending = False
        self.loop_cycle_index = 0
        self.status.loop_cycle_index = 0
        self._transport_diagnostics["loop_cycles_completed"] = 0
        self._transport_diagnostics["punch_start_hits"] = 0
        self._transport_diagnostics["punch_stop_hits"] = 0
        self._transport_diagnostics["auto_stop_events"] = 0
        self._transport_diagnostics["last_start_sample"] = 0
        self._transport_diagnostics["last_stop_sample"] = 0
        self._transport_diagnostics["last_auto_stop_sample"] = 0
        self._transport_last_error = ""
        self._last_start_action_ts = now

        for track_id in self.armed_tracks:
            track = self.engine.get_track(int(track_id))
            if track is not None:
                track.reset_recording_diagnostics()

        if self.loop_enabled:
            loop_length = int(self.loop_end_samples - self.loop_start_samples)
            self._loop_next_start_cursor = int(self.loop_start_samples)
            self._loop_next_end_cursor = int(self.loop_end_samples)
            if loop_length <= 0:
                self.status.last_error = "Invalid loop range"
                return False
        else:
            self._loop_next_start_cursor = None
            self._loop_next_end_cursor = None

        wait_for_start_marker = (
            (self.punch_enabled and self.punch_in_samples > 0)
            or (self.loop_enabled and self.loop_start_samples > 0)
        )

        self._punch_start_marker = max(0, self.punch_in_samples - self.pre_roll_samples)
        self._punch_stop_marker = None
        if self.punch_out_samples is not None:
            self._punch_stop_marker = self.punch_out_samples + self.post_roll_samples

        count_in_bars = max(0, self.metronome.config.count_in_bars)
        if count_in_bars > 0:
            self.status.count_in_active = True
            self.status.is_recording = False
            self._pending_count_in = self.metronome.count_in_block(count_in_bars)
            self._count_in_cursor = 0
            if wait_for_start_marker:
                self.metronome.start()
        elif wait_for_start_marker:
            self.status.count_in_active = False
            self.status.is_recording = False
            self.metronome.start()
        else:
            self.status.count_in_active = False
            self._begin_take_capture()

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
            self._transport_last_error = self.status.last_error

        input_audio = indata.T.copy()
        count_in_mix = np.zeros_like(input_audio)
        if self.status.count_in_active and self._pending_count_in is not None:
            remaining = self._pending_count_in.shape[1] - self._count_in_cursor
            copy_frames = min(frames, max(0, remaining))
            if copy_frames > 0:
                start = self._count_in_cursor
                end = start + copy_frames
                count_in_mix[:, :copy_frames] = self._pending_count_in[:, start:end]
                self._count_in_cursor = end

            if self._count_in_cursor >= self._pending_count_in.shape[1]:
                self.status.count_in_active = False
                self._pending_count_in = None
                self._count_in_cursor = 0
                self._transport_sample_cursor = 0
                if (self.punch_enabled and self.punch_in_samples > 0) or (self.loop_enabled and self.loop_start_samples > 0):
                    self.metronome.start()
                else:
                    self._begin_take_capture(start_metronome=not self.metronome.is_running)

        self._transport_sample_cursor += int(frames)
        if self.punch_enabled and not self.status.count_in_active:
            if not self.status.is_recording and self._transport_sample_cursor >= self._punch_start_marker:
                self._transport_diagnostics["punch_start_hits"] += 1
                self._begin_take_capture(start_metronome=not self.metronome.is_running)

            if (
                self.status.is_recording
                and self._punch_stop_marker is not None
                and self._transport_sample_cursor >= self._punch_stop_marker
            ):
                self._last_auto_stop_sample = int(self._transport_sample_cursor)
                self._transport_diagnostics["punch_stop_hits"] += 1
                self._transport_diagnostics["auto_stop_events"] += 1
                self._transport_diagnostics["last_auto_stop_sample"] = self._last_auto_stop_sample
                self.stop_recording(duration_seconds=0.0, level_stats={}, stop_stream=False, force=True)
                self._auto_stop_event_pending = True

        if self.loop_enabled and not self.status.count_in_active:
            loop_start_cursor = self._loop_next_start_cursor
            loop_end_cursor = self._loop_next_end_cursor

            if loop_start_cursor is not None and not self.status.is_recording and self._transport_sample_cursor >= loop_start_cursor:
                self._begin_take_capture(start_metronome=not self.metronome.is_running)

            if (
                loop_end_cursor is not None
                and self.status.is_recording
                and self._transport_sample_cursor >= loop_end_cursor
                and self.loop_end_samples is not None
            ):
                self._finalize_active_takes(duration_seconds=0.0, level_stats={})
                self._transport_diagnostics["loop_cycles_completed"] += 1
                self.loop_cycle_index += 1
                self.status.loop_cycle_index = self.loop_cycle_index
                self._start_new_takes_for_armed_tracks()

                loop_length = int(self.loop_end_samples - self.loop_start_samples)
                self._loop_next_start_cursor = int(loop_start_cursor + loop_length)
                self._loop_next_end_cursor = int(loop_end_cursor + loop_length)

        click = self.process_recording_block(input_audio)

        if self.status.is_recording:
            output = input_audio + click
        elif self.status.count_in_active:
            output = count_in_mix
        else:
            output = click

        if output.shape[0] < 2:
            output = np.vstack([output, output])

        outdata[:] = output.T[:frames]

    def stop_recording(
        self,
        duration_seconds: float = 0.0,
        level_stats: Optional[Dict[int, Dict[str, float]]] = None,
        stop_stream: bool = True,
        force: bool = False,
    ) -> None:
        now = time.monotonic()
        if not force and now - self._last_stop_action_ts < self._transport_action_debounce_sec:
            return
        self._last_stop_action_ts = now

        if not self.status.is_recording and not self.status.count_in_active and not self.active_take_ids:
            if stop_stream:
                self.stop_stream()
            return

        self.engine.stop_recording()
        self.metronome.stop()
        self.status.is_recording = False
        self.status.count_in_active = False
        self._pending_count_in = None
        self._count_in_cursor = 0
        self._transport_sample_cursor = 0
        self._loop_next_start_cursor = None
        self._loop_next_end_cursor = None
        self._punch_start_marker = 0
        self._punch_stop_marker = None
        self.status.last_auto_stop_sample = self._last_auto_stop_sample
        self._transport_diagnostics["last_stop_sample"] = int(self._transport_sample_cursor)
        self.loop_cycle_index = 0
        self.status.loop_cycle_index = 0

        self._finalize_active_takes(duration_seconds=duration_seconds, level_stats=level_stats)

        if self.auto_disarm_after_boundary and (self.punch_enabled or self.loop_enabled):
            self.clear_armed_tracks()

        self.session.save_session_metadata()
        if stop_stream:
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
            punch_enabled=self.punch_enabled,
            loop_enabled=self.loop_enabled,
            loop_cycle_index=self.loop_cycle_index,
            pre_roll_bars=self.samples_to_bars(self.pre_roll_samples),
            post_roll_bars=self.samples_to_bars(self.post_roll_samples),
            last_auto_stop_sample=self.status.last_auto_stop_sample,
        )
        return snapshot

    def consume_auto_stop_event(self) -> bool:
        if not self._auto_stop_event_pending:
            return False
        self._auto_stop_event_pending = False
        return True

    def get_transport_diagnostics(self) -> Dict[str, object]:
        diagnostics = dict(self._transport_diagnostics)
        diagnostics["last_transport_error"] = self._transport_last_error or self.status.last_error
        diagnostics["is_recording"] = bool(self.status.is_recording)
        diagnostics["count_in_active"] = bool(self.status.count_in_active)
        diagnostics["loop_enabled"] = bool(self.loop_enabled)
        diagnostics["punch_enabled"] = bool(self.punch_enabled)
        diagnostics["active_armed_tracks"] = len(self.armed_tracks)
        total_clip_events = 0
        active_silence_warnings = 0
        for track in self.engine.tracks:
            td = track.get_recording_diagnostics()
            total_clip_events += int(td.get("clip_events", 0))
            if bool(td.get("silence_warning_active", False)):
                active_silence_warnings += 1
        diagnostics["clip_events_total"] = total_clip_events
        diagnostics["silence_warnings_active"] = active_silence_warnings
        return diagnostics

    def undo_last_take(self):
        return self.session.undo_last_take()

    def redo_last_take(self):
        return self.session.redo_last_take()

    def get_track_takes(self, track_id: int):
        return self.session.get_all_takes_for_track(track_id)

    def set_active_take(self, track_id: int, take_number: int) -> bool:
        return self.session.set_active_take(track_id, take_number)

    def audition_take(self, track_id: int, take_number: int, loop: bool = False):
        """Preview one take directly from the recording buffer."""
        if self.status.is_recording or self.status.count_in_active:
            return False, "Cannot audition while recording is active"

        take = self.session.get_take(track_id, take_number)
        if take is None:
            return False, "Take not found"

        track = self.engine.get_track(track_id)
        if track is None:
            return False, "Track not found"

        audio = track.get_recorded_audio_segment(take.start_sample, take.end_sample)
        if audio.shape[1] == 0:
            return False, "Selected take has no recorded audio"

        try:
            sd.stop()
            sd.play(audio.T, samplerate=self.sample_rate, blocking=False, loop=loop)
            self.audition_active = True
            self.audition_looping = bool(loop)
            mode = "looping" if loop else "one-shot"
            return True, f"Auditioning take {take_number} on track {track_id} ({mode})"
        except Exception as exc:
            self.audition_active = False
            self.audition_looping = False
            return False, str(exc)

    def stop_audition(self) -> bool:
        """Stop any active audition playback."""
        try:
            sd.stop()
            was_active = self.audition_active
            self.audition_active = False
            self.audition_looping = False
            return was_active
        except Exception:
            self.audition_active = False
            self.audition_looping = False
            return False

    def export_take_to_wav(self, track_id: int, take_number: int) -> (bool, Optional[Path], str):
        """Persist one take segment to a WAV file for project-clip playback."""
        take = self.session.get_take(track_id, take_number)
        if take is None:
            return False, None, "Take not found"

        track = self.engine.get_track(track_id)
        if track is None:
            return False, None, "Track not found"

        audio = track.get_recorded_audio_segment(take.start_sample, take.end_sample)
        if audio.shape[1] == 0:
            return False, None, "Take has no audio"

        output_dir = ECHO_ROOT / "recorded_takes" / self.session.session_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"track_{track_id}_take_{take_number}.wav"

        try:
            sf.write(str(output_path), audio.T, self.sample_rate)
            return True, output_path, "ok"
        except Exception as exc:
            return False, None, str(exc)

    def get_meter_levels(self) -> Dict[int, Dict[str, float]]:
        levels: Dict[int, Dict[str, float]] = {}
        for track in self.engine.tracks:
            diagnostics = track.get_recording_diagnostics()
            levels[track.track_id] = {
                "current_db": track.current_level_db,
                "peak_db": track.peak_level_db,
                "clipping": 1.0 if track.clipping_detected else 0.0,
                "clip_events": int(diagnostics.get("clip_events", 0)),
                "peak_clip_hold_seconds": float(diagnostics.get("peak_clip_hold_seconds", 0.0)),
                "silence_warning": 1.0 if diagnostics.get("silence_warning_active", False) else 0.0,
                "silence_events": int(diagnostics.get("silence_events", 0)),
            }
        return levels

    def restore_session_preferences(self) -> None:
        """Restore persisted UI preferences for the current session id."""
        loaded = RecordingSession.load_session_metadata(self.session.session_id)
        if loaded is None:
            return
        self.session.ui_preferences = dict(getattr(loaded, "ui_preferences", self.session.ui_preferences))
