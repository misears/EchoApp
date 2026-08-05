"""Voice conversion helper for Echo Pro.

apply_voice_conversion() is the single call-site used by the UI to convert a
recorded WAV through an RVC voice profile.  It resolves the backend config
from voice_interface and normalises metadata fields on the result.
"""

from pathlib import Path

from voice_interface import (
    VoiceBackendConfig,
    VoiceProfileConfig,
    VoiceConvertRequest,
    VoiceConvertResult,
    get_default_voice_backend,
    get_voice_backend_capability,
    resolve_voice_model_path,
    voice_convert,
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
    model_path = resolve_voice_model_path()
    request = VoiceConvertRequest(
        source_wav=source_wav,
        target_profile=target_profile,
        preserve_pitch=preserve_pitch,
        preserve_formants=preserve_formants,
        strength=strength,
        notes=notes
    )
    result = voice_convert(request, output_path, backend)
    if "model_path" not in result.metadata:
        result.metadata["model_path"] = str(model_path)
    if "ready" not in result.metadata:
        result.metadata["ready"] = backend.extra.get("ready", False)
    if "reason" not in result.metadata:
        result.metadata["reason"] = backend.extra.get("reason", "")
    return result