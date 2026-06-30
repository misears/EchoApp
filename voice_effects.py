
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