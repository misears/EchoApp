
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Dict, Any

from app_paths import RVC_MODELS_DIR, ensure_dirs

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


def resolve_voice_model_path() -> Path:
    configured = os.environ.get("ECHO_RVC_MODEL_PATH", "").strip()
    if configured:
        return Path(configured)
    return RVC_MODELS_DIR / "current"


def get_voice_backend_capability() -> dict:
    ensure_dirs()
    model_path = resolve_voice_model_path()
    model_ready = model_path.exists()
    return {
        "backend": "RVC",
        "model_path": str(model_path),
        "ready": model_ready,
        "reason": "" if model_ready else "RVC voice conversion model not installed. Run install_echo_pro.bat install/update.",
    }


def get_default_voice_backend() -> VoiceBackendConfig:
    capability = get_voice_backend_capability()
    return VoiceBackendConfig(
        name="RVC",
        model_path=capability["model_path"],
        device="cpu",
        sample_rate=44100,
        extra={
            "ready": capability["ready"],
            "reason": capability["reason"],
        },
    )

def voice_convert(
    request: VoiceConvertRequest,
    output_path: Path,
    backend_config: VoiceBackendConfig,
) -> VoiceConvertResult:
    """
    Baseline implementation: slight gain change.
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
            "note": "Baseline conversion preview. Replace voice_convert with real model.",
            "preserve_pitch": request.preserve_pitch,
            "preserve_formants": request.preserve_formants,
            "strength": request.strength,
        }
    )