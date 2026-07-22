"""
Echo Pro Metronome
Generates tempo-synced click tracks for recording sessions.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


@dataclass
class MetronomeConfig:
    bpm: int = 120
    time_signature: Tuple[int, int] = (4, 4)
    sample_rate: int = 44100
    click_duration_ms: int = 20
    count_in_bars: int = 1
    click_level_db: float = -12.0
    accent_level_db: float = -6.0
    click_frequency_hz: int = 1800
    accent_frequency_hz: int = 2200


class Metronome:
    """Tempo-synced click generator with simple scheduling."""

    def __init__(self, config: Optional[MetronomeConfig] = None):
        self.config = config or MetronomeConfig()
        self.enabled = True
        self.is_running = False
        self._sample_position = 0
        self._beat_interval_samples = self._compute_beat_interval_samples()
        self._samples_per_bar = self._beat_interval_samples * self.config.time_signature[0]

    def _compute_beat_interval_samples(self) -> int:
        beats_per_minute = max(1, self.config.bpm)
        quarter_note_seconds = 60.0 / beats_per_minute
        beat_fraction = 4 / max(1, self.config.time_signature[1])
        return max(1, int(self.config.sample_rate * quarter_note_seconds * beat_fraction))

    def set_tempo(self, bpm: int) -> None:
        self.config.bpm = max(1, bpm)
        self._beat_interval_samples = self._compute_beat_interval_samples()
        self._samples_per_bar = self._beat_interval_samples * self.config.time_signature[0]

    def set_time_signature(self, numerator: int, denominator: int) -> None:
        self.config.time_signature = (max(1, numerator), max(1, denominator))
        self._beat_interval_samples = self._compute_beat_interval_samples()
        self._samples_per_bar = self._beat_interval_samples * self.config.time_signature[0]

    def reset(self) -> None:
        self._sample_position = 0
        self.is_running = False

    def start(self) -> None:
        self._sample_position = 0
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    def _click_wave(self, frequency_hz: int, duration_samples: int, amplitude: float) -> np.ndarray:
        if duration_samples <= 0:
            return np.zeros(0, dtype=np.float32)

        t = np.arange(duration_samples, dtype=np.float32) / float(self.config.sample_rate)
        envelope = np.exp(-t * 120.0)
        wave = np.sin(2.0 * np.pi * frequency_hz * t) * envelope * amplitude
        return wave.astype(np.float32)

    def _level_to_amplitude(self, db_value: float) -> float:
        return float(10 ** (db_value / 20.0))

    def render_block(self, num_frames: int) -> np.ndarray:
        """Render a stereo click block aligned to the current transport position."""
        output = np.zeros((2, num_frames), dtype=np.float32)

        if not self.enabled or not self.is_running or num_frames <= 0:
            self._sample_position += num_frames
            return output

        click_duration = max(1, int(self.config.sample_rate * self.config.click_duration_ms / 1000.0))
        click_amp = self._level_to_amplitude(self.config.click_level_db)
        accent_amp = self._level_to_amplitude(self.config.accent_level_db)
        beats_per_bar = max(1, self.config.time_signature[0])

        for frame_index in range(num_frames):
            absolute_sample = self._sample_position + frame_index
            if absolute_sample % self._beat_interval_samples == 0:
                beat_number = (absolute_sample // self._beat_interval_samples) % beats_per_bar
                is_accent = beat_number == 0
                frequency = self.config.accent_frequency_hz if is_accent else self.config.click_frequency_hz
                amplitude = accent_amp if is_accent else click_amp
                click = self._click_wave(frequency, click_duration, amplitude)
                click_length = min(click.shape[0], num_frames - frame_index)
                if click_length > 0:
                    output[0, frame_index:frame_index + click_length] += click[:click_length]
                    output[1, frame_index:frame_index + click_length] += click[:click_length]

        self._sample_position += num_frames
        return output

    def count_in_block(self, bars: Optional[int] = None) -> np.ndarray:
        """Render a count-in click track for the configured number of bars."""
        bars = self.config.count_in_bars if bars is None else max(0, bars)
        total_samples = self._samples_per_bar * bars
        self.start()
        block = self.render_block(total_samples)
        self.stop()
        return block
