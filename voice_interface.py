
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any

@dataclass
class VoiceBackendConfig:
    name: str
    model_path: str
    device: str
    sample_rate: int
    extra: Dict[str, Any] = field(default_factory=dict)

@dataclass
class VoiceProfileConfig:
    name: str
    embedding_path: str
    source_audio_path: str
    consent_flag: bool
    source_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)

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
    import numpy as np
    import soundfile as sf

    data, samplerate = sf.read(str(request.source_wav), always_2d=False)
    # Apply gain: strength=1.0 → no change; <1.0 → quieter; >1.0 → louder
    gain_linear = 10.0 ** ((request.strength - 1.0) * 3.0 / 20.0)
    converted = np.clip(data * gain_linear, -1.0, 1.0)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), converted, samplerate, subtype="PCM_16")

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