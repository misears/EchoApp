"""
Echo Pro Audio Engine — Core real-time audio processing
Handles multi-track recording, playback, effects chains, and low-latency monitoring.
"""

import numpy as np
from collections import deque
from threading import Lock
from typing import Callable, List, Optional, Tuple
import sounddevice as sd

class AudioBuffer:
    """Ring buffer for real-time audio processing."""
    
    def __init__(self, channels: int, sample_rate: int, duration_seconds: float):
        """
        Args:
            channels: Number of audio channels
            sample_rate: Samples per second
            duration_seconds: Total buffer duration in seconds
        """
        self.channels = channels
        self.sample_rate = sample_rate
        self.size = int(sample_rate * duration_seconds)
        self.position = 0
        self.lock = Lock()
        
        # Ring buffer: shape (channels, size)
        self.buffer = np.zeros((channels, self.size), dtype=np.float32)
    
    def write(self, audio: np.ndarray) -> None:
        """Write audio data to buffer.
        
        Args:
            audio: Array of shape (samples, channels) or (channels, samples)
        """
        with self.lock:
            if audio.shape[0] != self.channels:
                # Transpose if needed
                audio = audio.T
            
            samples = audio.shape[1]
            
            # Handle wrap-around
            if self.position + samples <= self.size:
                self.buffer[:, self.position:self.position + samples] = audio
            else:
                # Split write (wrap around)
                end_space = self.size - self.position
                self.buffer[:, self.position:] = audio[:, :end_space]
                self.buffer[:, :samples - end_space] = audio[:, end_space:]
            
            self.position = (self.position + samples) % self.size
    
    def read(self, num_samples: int, offset: int = 0) -> np.ndarray:
        """Read audio data from buffer.
        
        Args:
            num_samples: Number of samples to read per channel
            offset: Read offset in samples
        
        Returns:
            Array of shape (channels, num_samples)
        """
        with self.lock:
            result = np.zeros((self.channels, num_samples), dtype=np.float32)
            
            for i in range(num_samples):
                pos = (self.position + offset + i) % self.size
                result[:, i] = self.buffer[:, pos]
            
            return result
    
    def get_current_position(self) -> int:
        """Get current write position in samples."""
        with self.lock:
            return self.position


class PluginChain:
    """Manages a chain of audio effects/plugins."""
    
    def __init__(self, max_plugins: int = 10):
        self.plugins: List['AudioPlugin'] = []
        self.max_plugins = max_plugins
        self.bypass = False
        self.lock = Lock()
    
    def add_plugin(self, plugin: 'AudioPlugin', position: Optional[int] = None) -> bool:
        """Add plugin to chain.
        
        Args:
            plugin: Plugin to add
            position: Insert position (None = end)
        
        Returns:
            True if added, False if chain is full
        """
        with self.lock:
            if len(self.plugins) >= self.max_plugins:
                return False
            
            if position is None:
                self.plugins.append(plugin)
            else:
                self.plugins.insert(position, plugin)
            
            return True
    
    def remove_plugin(self, index: int) -> bool:
        """Remove plugin at index."""
        with self.lock:
            if 0 <= index < len(self.plugins):
                self.plugins.pop(index)
                return True
            return False
    
    def move_plugin(self, from_idx: int, to_idx: int) -> bool:
        """Reorder plugin chain."""
        with self.lock:
            if 0 <= from_idx < len(self.plugins) and 0 <= to_idx < len(self.plugins):
                plugin = self.plugins.pop(from_idx)
                self.plugins.insert(to_idx, plugin)
                return True
            return False
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """Process audio through all plugins in chain.
        
        Args:
            audio: Input audio, shape (channels, samples)
        
        Returns:
            Processed audio
        """
        if self.bypass:
            return audio
        
        with self.lock:
            result = audio.copy()
            for plugin in self.plugins:
                if not plugin.bypassed:
                    result = plugin.process(result)
            return result
    
    def bypass_all(self) -> None:
        self.bypass = True
    
    def enable_all(self) -> None:
        self.bypass = False


class AudioPlugin:
    """Base class for audio effects plugins."""
    
    def __init__(self, name: str, sample_rate: int):
        self.name = name
        self.sample_rate = sample_rate
        self.bypassed = False
        self.parameters = {}
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """Process audio block.
        
        Args:
            audio: Input audio, shape (channels, samples)
        
        Returns:
            Processed audio
        """
        if self.bypassed:
            return audio
        return audio
    
    def set_parameter(self, name: str, value: float) -> None:
        """Set effect parameter."""
        if name in self.parameters:
            self.parameters[name] = value
    
    def get_parameter(self, name: str) -> Optional[float]:
        """Get effect parameter value."""
        return self.parameters.get(name)


class Track:
    """Audio track with recording, playback, and effects."""
    
    def __init__(self, track_id: int, name: str, channels: int, sample_rate: int):
        self.track_id = track_id
        self.name = name
        self.channels = channels
        self.sample_rate = sample_rate
        
        # Recording and playback
        self.recording_buffer = AudioBuffer(channels, sample_rate, 300)  # 5 min buffer
        self.playback_position = 0
        
        # Effects chain
        self.effects_chain = PluginChain(max_plugins=10)
        
        # Volume and panning
        self.volume_db = 0.0
        self.pan = 0.0  # -1.0 = left, 0.0 = center, 1.0 = right
        self.muted = False
        self.soloed = False
        
        # Gain metering
        self.current_level_db = -80.0
        self.peak_level_db = -80.0
        self.clipping_detected = False
        
        self.lock = Lock()
    
    def record(self, audio: np.ndarray) -> None:
        """Record audio to this track."""
        if self.muted:
            return
        self.recording_buffer.write(audio)

        # Update metering from recorded input so recording meters stay live.
        rms = np.sqrt(np.mean(audio ** 2))
        current_db = 20 * np.log10(rms + 1e-10)
        peak = float(np.max(np.abs(audio)))
        peak_db = 20 * np.log10(peak + 1e-10)

        with self.lock:
            self.current_level_db = current_db
            self.peak_level_db = peak_db
            self.clipping_detected = peak > 1.0
    
    def get_playback_audio(self, num_samples: int) -> np.ndarray:
        """Get audio for playback."""
        with self.lock:
            audio = self.recording_buffer.read(num_samples)
            
            # Apply effects
            audio = self.effects_chain.process(audio)
            
            # Apply volume
            db_linear = 10 ** (self.volume_db / 20.0)
            audio = audio * db_linear
            
            # Apply panning (simple linear pan)
            if self.pan != 0.0:
                if self.pan > 0:  # Right pan
                    audio[0] *= (1.0 - self.pan)  # Reduce left
                else:  # Left pan
                    audio[1] *= (1.0 + self.pan)  # Reduce right
            
            # Measure level
            rms = np.sqrt(np.mean(audio ** 2))
            self.current_level_db = 20 * np.log10(rms + 1e-10)
            peak = np.max(np.abs(audio))
            self.peak_level_db = 20 * np.log10(peak + 1e-10)
            self.clipping_detected = peak > 1.0
            
            return audio
    
    def set_volume_db(self, db: float) -> None:
        """Set track volume in dB."""
        with self.lock:
            self.volume_db = np.clip(db, -80, 20)
    
    def get_volume_db(self) -> float:
        """Get track volume in dB."""
        return self.volume_db


class AudioEngine:
    """Main audio engine coordinating multi-track recording and playback."""
    
    def __init__(self, num_tracks: int = 8, sample_rate: int = 44100, buffer_size: int = 256):
        self.num_tracks = num_tracks
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        
        # Tracks
        self.tracks: List[Track] = []
        for i in range(num_tracks):
            self.tracks.append(Track(i, f"Track {i+1}", 2, sample_rate))
        
        # Recording/playback state
        self.is_recording = False
        self.is_playing = False
        self.recording_start_time = 0
        
        # Audio I/O stream
        self.stream = None
        self.lock = Lock()
        
        # Monitoring
        self.input_monitoring_enabled = True
        self.monitoring_volume = 0.0  # dB
    
    def start_stream(self, input_device: Optional[int] = None, 
                     output_device: Optional[int] = None) -> bool:
        """Start audio I/O stream."""
        try:
            self.stream = sd.Stream(
                device=(input_device, output_device),
                samplerate=self.sample_rate,
                blocksize=self.buffer_size,
                channels=2,
                dtype=np.float32,
                callback=self._audio_callback,
                latency='low'
            )
            self.stream.start()
            return True
        except Exception as e:
            print(f"Error starting audio stream: {e}")
            return False
    
    def stop_stream(self) -> None:
        """Stop audio I/O stream."""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
    
    def _audio_callback(self, indata: np.ndarray, outdata: np.ndarray, 
                       frames: int, time_info, status):
        """Real-time audio callback (called by sounddevice)."""
        if status:
            print(f"Audio callback status: {status}")
        
        # Input monitoring and recording
        input_audio = indata.T.copy()  # (2, frames)
        
        if self.is_recording:
            self.tracks[0].record(input_audio)
        
        # Playback with effects
        output = np.zeros((2, frames), dtype=np.float32)
        
        for track in self.tracks:
            if not track.muted or track.soloed:
                track_audio = track.get_playback_audio(frames)
                output += track_audio
        
        # Soft clip to prevent harshness
        output = np.tanh(output)
        
        # Output
        outdata[:] = output.T
    
    def start_recording(self) -> None:
        """Start recording on all tracks."""
        with self.lock:
            self.is_recording = True
    
    def stop_recording(self) -> None:
        """Stop recording."""
        with self.lock:
            self.is_recording = False
    
    def start_playback(self) -> None:
        """Start playback of all tracks."""
        with self.lock:
            self.is_playing = True
    
    def stop_playback(self) -> None:
        """Stop playback."""
        with self.lock:
            self.is_playing = False
    
    def get_track(self, track_id: int) -> Optional[Track]:
        """Get track by ID."""
        if 0 <= track_id < len(self.tracks):
            return self.tracks[track_id]
        return None
    
    def get_all_levels(self) -> List[Tuple[float, float, bool]]:
        """Get (current_db, peak_db, clipping) for all tracks."""
        return [(t.current_level_db, t.peak_level_db, t.clipping_detected) 
                for t in self.tracks]
