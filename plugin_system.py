"""
Echo Pro Plugin System — Effect plugin architecture for audio processing.
Provides base classes and common effects for the effects chain.
"""

import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple
import math

class AudioPlugin(ABC):
    """Base class for all audio effects plugins."""
    
    def __init__(self, name: str, sample_rate: int, channels: int = 2):
        self.name = name
        self.sample_rate = sample_rate
        self.channels = channels
        self.bypassed = False
        self.parameters: Dict[str, float] = {}
        self.wet_dry_mix = 1.0  # 0 = all dry, 1 = all wet
    
    @abstractmethod
    def process(self, audio: np.ndarray) -> np.ndarray:
        """Process audio block.
        
        Args:
            audio: Input audio, shape (channels, samples)
        
        Returns:
            Processed audio, same shape as input
        """
        pass
    
    def set_parameter(self, name: str, value: float) -> None:
        """Set effect parameter."""
        if name in self.parameters:
            self.parameters[name] = value
        elif name == "bypass":
            self.bypassed = bool(value)
        elif name == "mix":
            self.wet_dry_mix = np.clip(value, 0.0, 1.0)
    
    def get_parameter(self, name: str) -> Optional[float]:
        """Get effect parameter value."""
        if name == "bypass":
            return float(self.bypassed)
        elif name == "mix":
            return self.wet_dry_mix
        return self.parameters.get(name)
    
    def list_parameters(self) -> Dict[str, Tuple[float, float, float]]:
        """List (min, default, max) for all parameters."""
        return {}


class Gain(AudioPlugin):
    """Simple gain/attenuation effect."""
    
    def __init__(self, sample_rate: int, channels: int = 2):
        super().__init__("Gain", sample_rate, channels)
        self.parameters = {
            "gain_db": 0.0
        }
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply gain in dB."""
        if self.bypassed:
            return audio
        
        gain_linear = 10 ** (self.parameters["gain_db"] / 20.0)
        return audio * gain_linear
    
    def list_parameters(self) -> Dict[str, Tuple[float, float, float]]:
        return {
            "gain_db": (-80.0, 0.0, 20.0)
        }


class Limiter(AudioPlugin):
    """Peak limiter to prevent clipping."""
    
    def __init__(self, sample_rate: int, channels: int = 2):
        super().__init__("Limiter", sample_rate, channels)
        self.parameters = {
            "threshold_db": -0.1,
            "release_ms": 100.0
        }
        self.release_samples = int(sample_rate * 0.1 / 1000.0)
        self.envelope = 0.0
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply soft-knee limiting."""
        if self.bypassed:
            return audio
        
        threshold_linear = 10 ** (self.parameters["threshold_db"] / 20.0)
        release_coeff = 1.0 / max(1, self.release_samples)
        
        output = audio.copy()
        
        for ch in range(self.channels):
            for i in range(audio.shape[1]):
                sample = abs(audio[ch, i])
                
                # Smooth envelope
                self.envelope = max(sample, self.envelope * (1.0 - release_coeff))
                
                # Apply limiting
                if self.envelope > threshold_linear:
                    gain = threshold_linear / max(self.envelope, 1e-10)
                    output[ch, i] *= gain
        
        return output
    
    def list_parameters(self) -> Dict[str, Tuple[float, float, float]]:
        return {
            "threshold_db": (-20.0, -0.1, 0.0),
            "release_ms": (10.0, 100.0, 1000.0)
        }


class SimpleEQ(AudioPlugin):
    """3-band parametric EQ (Low, Mid, High)."""
    
    def __init__(self, sample_rate: int, channels: int = 2):
        super().__init__("EQ", sample_rate, channels)
        self.parameters = {
            "low_gain_db": 0.0,      # < 250 Hz
            "mid_gain_db": 0.0,      # 250 - 4000 Hz
            "high_gain_db": 0.0      # > 4000 Hz
        }
        
        # Simple one-pole filters for band splitting
        self.low_cutoff = 250
        self.high_cutoff = 4000
        self._update_coeffs()
    
    def _update_coeffs(self) -> None:
        """Update filter coefficients based on sample rate."""
        # Simplified 1st-order filter coefficients
        self.low_coeff = 2 * math.pi * self.low_cutoff / self.sample_rate
        self.high_coeff = 2 * math.pi * self.high_cutoff / self.sample_rate
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply 3-band EQ."""
        if self.bypassed:
            return audio
        
        output = audio.copy()
        
        # Apply gain to each frequency band
        low_gain = 10 ** (self.parameters["low_gain_db"] / 20.0)
        mid_gain = 10 ** (self.parameters["mid_gain_db"] / 20.0)
        high_gain = 10 ** (self.parameters["high_gain_db"] / 20.0)
        
        # Simplified approach: just scale frequencies
        # In production, use proper DSP (FFT or IIR filters)
        output = output * 0.333 * (low_gain + mid_gain + high_gain)
        
        return output
    
    def list_parameters(self) -> Dict[str, Tuple[float, float, float]]:
        return {
            "low_gain_db": (-12.0, 0.0, 12.0),
            "mid_gain_db": (-12.0, 0.0, 12.0),
            "high_gain_db": (-12.0, 0.0, 12.0)
        }


class Compressor(AudioPlugin):
    """Dynamic range compressor."""
    
    def __init__(self, sample_rate: int, channels: int = 2):
        super().__init__("Compressor", sample_rate, channels)
        self.parameters = {
            "threshold_db": -20.0,
            "ratio": 4.0,
            "attack_ms": 10.0,
            "release_ms": 100.0,
            "makeup_gain_db": 0.0
        }
        self.envelope = 0.0
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply dynamic compression."""
        if self.bypassed:
            return audio
        
        threshold_linear = 10 ** (self.parameters["threshold_db"] / 20.0)
        ratio = self.parameters["ratio"]
        makeup_gain = 10 ** (self.parameters["makeup_gain_db"] / 20.0)
        
        attack_samples = int(self.sample_rate * self.parameters["attack_ms"] / 1000.0)
        release_samples = int(self.sample_rate * self.parameters["release_ms"] / 1000.0)
        
        attack_coeff = 1.0 / max(1, attack_samples)
        release_coeff = 1.0 / max(1, release_samples)
        
        output = audio.copy()
        
        for ch in range(self.channels):
            for i in range(audio.shape[1]):
                sample = abs(audio[ch, i])
                
                # Envelope follower
                if sample > self.envelope:
                    self.envelope = attack_coeff * sample + (1 - attack_coeff) * self.envelope
                else:
                    self.envelope = release_coeff * sample + (1 - release_coeff) * self.envelope
                
                # Gain reduction
                if self.envelope > threshold_linear:
                    gain_reduction_db = (threshold_linear / max(self.envelope, 1e-10))
                    gain_reduction = (1 - 1/ratio) * gain_reduction_db
                    output[ch, i] *= gain_reduction * makeup_gain
                else:
                    output[ch, i] *= makeup_gain
        
        return output
    
    def list_parameters(self) -> Dict[str, Tuple[float, float, float]]:
        return {
            "threshold_db": (-60.0, -20.0, 0.0),
            "ratio": (1.0, 4.0, 16.0),
            "attack_ms": (0.1, 10.0, 100.0),
            "release_ms": (10.0, 100.0, 1000.0),
            "makeup_gain_db": (-20.0, 0.0, 20.0)
        }


class Reverb(AudioPlugin):
    """Simple reverb using feedback delays."""
    
    def __init__(self, sample_rate: int, channels: int = 2):
        super().__init__("Reverb", sample_rate, channels)
        self.parameters = {
            "room_size": 0.5,  # 0-1
            "damping": 0.5,    # 0-1
            "width": 1.0,      # 0-1
            "wet_level": 0.3,  # 0-1
            "dry_level": 0.7   # 0-1
        }
        
        # Feedback delay lines
        self.delay_buffers = [
            np.zeros(int(sample_rate * 0.05)),  # 50ms
            np.zeros(int(sample_rate * 0.08)),  # 80ms
        ]
        self.delay_positions = [0, 0]
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply reverb effect."""
        if self.bypassed:
            return audio
        
        output = np.zeros_like(audio)
        room_size = self.parameters["room_size"]
        wet_level = self.parameters["wet_level"]
        dry_level = self.parameters["dry_level"]
        
        for ch in range(self.channels):
            for i in range(audio.shape[1]):
                sample = audio[ch, i]
                
                # Sum delayed samples
                wet = 0.0
                for delay_idx, delay_buf in enumerate(self.delay_buffers):
                    wet += delay_buf[self.delay_positions[delay_idx]]
                    
                    # Feedback
                    new_sample = sample + wet * room_size
                    delay_buf[self.delay_positions[delay_idx]] = new_sample
                    
                    # Advance position
                    self.delay_positions[delay_idx] = (self.delay_positions[delay_idx] + 1) % len(delay_buf)
                
                # Mix wet and dry
                output[ch, i] = dry_level * sample + wet_level * wet
        
        return output
    
    def list_parameters(self) -> Dict[str, Tuple[float, float, float]]:
        return {
            "room_size": (0.0, 0.5, 1.0),
            "damping": (0.0, 0.5, 1.0),
            "width": (0.0, 1.0, 1.0),
            "wet_level": (0.0, 0.3, 1.0),
            "dry_level": (0.0, 0.7, 1.0)
        }


class PluginFactory:
    """Factory for creating audio plugins."""
    
    _PLUGINS = {
        "Gain": Gain,
        "Limiter": Limiter,
        "EQ": SimpleEQ,
        "Compressor": Compressor,
        "Reverb": Reverb
    }
    
    @classmethod
    def create_plugin(cls, plugin_name: str, sample_rate: int, 
                     channels: int = 2) -> Optional[AudioPlugin]:
        """Create a plugin by name."""
        if plugin_name in cls._PLUGINS:
            return cls._PLUGINS[plugin_name](sample_rate, channels)
        return None
    
    @classmethod
    def list_plugins(cls) -> list:
        """List all available plugins."""
        return list(cls._PLUGINS.keys())
    
    @classmethod
    def register_plugin(cls, name: str, plugin_class) -> None:
        """Register a custom plugin."""
        cls._PLUGINS[name] = plugin_class
