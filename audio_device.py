"""
Echo Pro Audio Device Manager — Audio device detection and configuration.
Handles input/output device selection, capabilities, and fallback handling.
"""

import sounddevice as sd
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
import shutil

from app_paths import ECHO_ROOT

@dataclass
class AudioDevice:
    """Information about an audio device."""
    device_id: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_sample_rate: float
    default_latency_ms: float
    is_default_input: bool
    is_default_output: bool
    api: str
    
    def is_input_capable(self) -> bool:
        return self.max_input_channels > 0
    
    def is_output_capable(self) -> bool:
        return self.max_output_channels > 0
    
    def get_channels(self, mode: str) -> int:
        """Get number of usable channels for mode ('input' or 'output')."""
        if mode == 'input':
            return min(self.max_input_channels, 2)
        else:
            return min(self.max_output_channels, 2)


class AudioDeviceManager:
    """Manages audio device detection and configuration."""
    
    def __init__(self):
        self.devices: List[AudioDevice] = []
        self.selected_input_device: Optional[int] = None
        self.selected_output_device: Optional[int] = None
        self.selected_sample_rate: int = 44100
        self.selected_buffer_size: int = 256
        
        self.refresh_devices()
    
    def refresh_devices(self) -> None:
        """Scan for available audio devices."""
        self.devices = []

        def _coerce_latency_seconds(device: dict) -> float:
            values = []

            default_latency = device.get('default_latency')
            if isinstance(default_latency, (list, tuple)):
                values.extend(v for v in default_latency if isinstance(v, (int, float)))
            elif isinstance(default_latency, dict):
                values.extend(v for v in default_latency.values() if isinstance(v, (int, float)))
            elif isinstance(default_latency, (int, float)):
                values.append(default_latency)

            for key in (
                'default_low_input_latency',
                'default_low_output_latency',
                'default_high_input_latency',
                'default_high_output_latency',
            ):
                val = device.get(key)
                if isinstance(val, (int, float)):
                    values.append(val)

            numeric = [float(v) for v in values if float(v) >= 0.0]
            if not numeric:
                return 0.0
            return min(numeric)
        
        try:
            device_list = sd.query_devices()
            default_pair = sd.default.device
            default_input = default_pair[0] if isinstance(default_pair, (list, tuple)) and len(default_pair) > 0 else -1
            default_output = default_pair[1] if isinstance(default_pair, (list, tuple)) and len(default_pair) > 1 else -1
            if not isinstance(default_input, int):
                default_input = -1
            if not isinstance(default_output, int):
                default_output = -1
            
            for i, device in enumerate(device_list):
                latency_seconds = _coerce_latency_seconds(device)
                audio_device = AudioDevice(
                    device_id=i,
                    name=device['name'],
                    max_input_channels=device['max_input_channels'],
                    max_output_channels=device['max_output_channels'],
                    default_sample_rate=device['default_samplerate'],
                    default_latency_ms=latency_seconds * 1000.0,
                    is_default_input=(i == default_input),
                    is_default_output=(i == default_output),
                    api=device.get('hostapi', 'Unknown')
                )
                self.devices.append(audio_device)
            
            # Set defaults
            if default_input >= 0:
                self.selected_input_device = default_input
            if default_output >= 0:
                self.selected_output_device = default_output
                
        except Exception as e:
            print(f"Error scanning audio devices: {e}")
    
    def get_input_devices(self) -> List[AudioDevice]:
        """Get all available input devices."""
        return [d for d in self.devices if d.is_input_capable()]
    
    def get_output_devices(self) -> List[AudioDevice]:
        """Get all available output devices."""
        return [d for d in self.devices if d.is_output_capable()]
    
    def get_device(self, device_id: int) -> Optional[AudioDevice]:
        """Get device by ID."""
        for device in self.devices:
            if device.device_id == device_id:
                return device
        return None
    
    def select_input_device(self, device_id: int) -> bool:
        """Select input device."""
        device = self.get_device(device_id)
        if device and device.is_input_capable():
            self.selected_input_device = device_id
            return True
        return False
    
    def select_output_device(self, device_id: int) -> bool:
        """Select output device."""
        device = self.get_device(device_id)
        if device and device.is_output_capable():
            self.selected_output_device = device_id
            return True
        return False
    
    def set_sample_rate(self, sample_rate: int) -> bool:
        """Set sample rate. Common rates: 44100, 48000, 96000."""
        if sample_rate in [44100, 48000, 96000, 192000]:
            self.selected_sample_rate = sample_rate
            return True
        return False
    
    def set_buffer_size(self, buffer_size: int) -> bool:
        """Set buffer size. Common: 64, 128, 256, 512, 1024."""
        if buffer_size in [64, 128, 256, 512, 1024]:
            self.selected_buffer_size = buffer_size
            return True
        return False
    
    def get_input_latency(self) -> float:
        """Get estimated input latency in milliseconds."""
        device = self.get_device(self.selected_input_device)
        if device:
            # Latency = (buffer_size / sample_rate) * 1000 + device latency
            buffer_latency = (self.selected_buffer_size / self.selected_sample_rate) * 1000
            return buffer_latency + device.default_latency_ms
        return 0.0
    
    def get_output_latency(self) -> float:
        """Get estimated output latency in milliseconds."""
        device = self.get_device(self.selected_output_device)
        if device:
            buffer_latency = (self.selected_buffer_size / self.selected_sample_rate) * 1000
            return buffer_latency + device.default_latency_ms
        return 0.0
    
    def get_total_latency(self) -> float:
        """Get total round-trip latency."""
        return self.get_input_latency() + self.get_output_latency()
    
    def test_device_configuration(self) -> Tuple[bool, str]:
        """Test if current device configuration works.
        
        Returns:
            (success, message)
        """
        try:
            input_dev = self.get_device(self.selected_input_device)
            output_dev = self.get_device(self.selected_output_device)
            
            if not input_dev or not output_dev:
                return False, "Device not found"

            compatible, message = self.check_channel_compatibility(
                input_device_id=self.selected_input_device,
                output_device_id=self.selected_output_device,
                required_input_channels=2,
                required_output_channels=2,
            )
            if not compatible:
                return False, message
            
            # Try to open a short test stream
            with sd.Stream(
                device=(self.selected_input_device, self.selected_output_device),
                samplerate=self.selected_sample_rate,
                blocksize=self.selected_buffer_size,
                channels=2,
                dtype='float32',
                latency='low'
            ):
                pass
            
            return True, "Device configuration OK"
            
        except Exception as e:
            return False, f"Device error: {str(e)}"

    def check_channel_compatibility(
        self,
        input_device_id: Optional[int] = None,
        output_device_id: Optional[int] = None,
        required_input_channels: int = 2,
        required_output_channels: int = 2,
    ) -> Tuple[bool, str]:
        input_id = self.selected_input_device if input_device_id is None else int(input_device_id)
        output_id = self.selected_output_device if output_device_id is None else int(output_device_id)

        input_dev = self.get_device(input_id)
        output_dev = self.get_device(output_id)
        if input_dev is None or output_dev is None:
            return False, "Selected input/output devices are not available"

        if input_dev.max_input_channels < int(required_input_channels):
            return False, (
                f"Input device '{input_dev.name}' supports only {input_dev.max_input_channels} channel(s); "
                f"{required_input_channels} required"
            )

        if output_dev.max_output_channels < int(required_output_channels):
            return False, (
                f"Output device '{output_dev.name}' supports only {output_dev.max_output_channels} channel(s); "
                f"{required_output_channels} required"
            )

        return True, "Channel compatibility OK"

    def get_preflight_summary(
        self,
        required_input_channels: int = 2,
        required_output_channels: int = 2,
        min_free_space_gb: float = 1.0,
    ) -> Dict[str, object]:
        input_dev = self.get_device(self.selected_input_device) if self.selected_input_device is not None else None
        output_dev = self.get_device(self.selected_output_device) if self.selected_output_device is not None else None

        compatible, compat_message = self.check_channel_compatibility(
            required_input_channels=required_input_channels,
            required_output_channels=required_output_channels,
        )

        disk = shutil.disk_usage(str(ECHO_ROOT))
        free_gb = float(disk.free) / (1024.0 ** 3)

        warnings: List[str] = []
        if not compatible:
            warnings.append(compat_message)
        if free_gb < float(min_free_space_gb):
            warnings.append(
                f"Low disk space near recording root: {free_gb:.2f} GB free (recommended >= {min_free_space_gb:.2f} GB)"
            )

        return {
            "input_device": input_dev.name if input_dev else "None",
            "output_device": output_dev.name if output_dev else "None",
            "sample_rate": int(self.selected_sample_rate),
            "buffer_size": int(self.selected_buffer_size),
            "input_latency_ms": float(self.get_input_latency()),
            "output_latency_ms": float(self.get_output_latency()),
            "total_latency_ms": float(self.get_total_latency()),
            "disk_free_gb": free_gb,
            "channel_compatible": bool(compatible),
            "warnings": warnings,
        }

    def format_preflight_summary(self, summary: Dict[str, object]) -> str:
        lines = [
            f"Input: {summary.get('input_device', 'None')}",
            f"Output: {summary.get('output_device', 'None')}",
            f"Sample Rate: {summary.get('sample_rate', 0)} Hz",
            f"Buffer Size: {summary.get('buffer_size', 0)}",
            f"Input Latency: {float(summary.get('input_latency_ms', 0.0)):.1f} ms",
            f"Output Latency: {float(summary.get('output_latency_ms', 0.0)):.1f} ms",
            f"Round Trip Latency: {float(summary.get('total_latency_ms', 0.0)):.1f} ms",
            f"Disk Free: {float(summary.get('disk_free_gb', 0.0)):.2f} GB",
        ]
        warnings = list(summary.get("warnings", []))
        if warnings:
            lines.append("Warnings:")
            for warning in warnings:
                lines.append(f"- {warning}")
        return "\n".join(lines)
    
    def get_device_summary(self) -> Dict:
        """Get summary of current configuration."""
        input_dev = self.get_device(self.selected_input_device)
        output_dev = self.get_device(self.selected_output_device)
        
        return {
            "input_device": input_dev.name if input_dev else "None",
            "output_device": output_dev.name if output_dev else "None",
            "sample_rate": self.selected_sample_rate,
            "buffer_size": self.selected_buffer_size,
            "input_latency_ms": self.get_input_latency(),
            "output_latency_ms": self.get_output_latency(),
            "total_latency_ms": self.get_total_latency(),
            "total_devices": len(self.devices)
        }
    
    def list_devices_info(self) -> str:
        """Get readable list of all devices."""
        lines = []
        lines.append("Available Audio Devices:")
        lines.append("-" * 80)
        
        for device in self.devices:
            marker = ""
            if device.is_default_input:
                marker += "[Input Default]"
            if device.is_default_output:
                marker += "[Output Default]"
            
            lines.append(f"{device.device_id:2d} | {device.name:40s} | "
                        f"In:{device.max_input_channels} Out:{device.max_output_channels} | "
                        f"{device.default_sample_rate:.0f}Hz {marker}")
        
        return "\n".join(lines)


# Global device manager instance
device_manager = AudioDeviceManager()
