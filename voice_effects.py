
import os
from pathlib import Path

from voice_interface import (
    VoiceBackendConfig,
    VoiceProfileConfig,
    VoiceConvertRequest,
    VoiceConvertResult,
    voice_convert,
)
from app_paths import RVC_MODELS_DIR, ensure_dirs


def _resolve_rvc_model_path() -> Path:
    configured = os.environ.get("ECHO_RVC_MODEL_PATH", "").strip()
    if configured:
        return Path(configured)
    return RVC_MODELS_DIR / "current"


def get_voice_backend_capability() -> dict:
    ensure_dirs()
    model_path = _resolve_rvc_model_path()
    model_ready = model_path.exists()
    return {
        "backend": "RVC",
        "model_path": str(model_path),
        "ready": model_ready,
        "reason": "" if model_ready else "RVC model assets not found. Run install_echo_pro.bat install/update.",
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
        }
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
    if "ready" not in result.metadata:
        result.metadata["ready"] = backend.extra.get("ready", False)
    if "reason" not in result.metadata:
        result.metadata["reason"] = backend.extra.get("reason", "")
    return result