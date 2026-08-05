"""Text-to-music interface contract for Echo Pro.

Defines the data classes (T2MModelConfig, T2MClipRequest, T2MClipResult) and
the t2m_generate_clip() entry point.  The baseline implementation produces a
silent placeholder clip; replace the function body to plug in a real model.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Literal, Dict, Any

StyleType = Literal["lofi", "rock", "pop", "edm", "orchestral", "jazz", "hiphop", "ambient", "custom"]
VocalMode = Literal["none", "lead", "choir", "backing"]
BackendType = Literal["offline", "cloud"]

@dataclass
class T2MModelConfig:
    name: str
    backend_type: BackendType

    max_clip_seconds: int
    sample_rate: int
    stereo: bool
    fp16: bool
    batch_size: int

    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class T2MClipRequest:
    prompt_style: StyleType
    prompt_genre: str
    prompt_mood: str
    lyrics: str
    vocal_mode: VocalMode

    key: str
    chords: str
    time_signature: str
    tempo_bpm: int

    duration_seconds: int
    seed: Optional[int] = None

    section_name: str = ""
    notes: str = ""


@dataclass
class T2MClipResult:
    audio_path: Path
    duration_ms: int
    used_seed: Optional[int]
    backend_name: str
    metadata: Dict[str, Any]


def t2m_generate_clip(
    request: T2MClipRequest,
    output_path: Path,
    model_config: T2MModelConfig,
) -> T2MClipResult:
    """
    Baseline implementation: generates a silent preview clip.
    Replace this body with a real T2M model.
    """
    import numpy as _np
    import soundfile as _sf

    duration_ms = request.duration_seconds * 1000
    sample_rate = model_config.sample_rate
    n_channels = 2 if model_config.stereo else 1
    n_frames = int(sample_rate * request.duration_seconds)
    requested_format = str(model_config.extra.get("requested_output_format", "wav") or "wav").strip().lower()
    normalize_output = bool(model_config.extra.get("normalize_output", True))
    output_format = requested_format if requested_format in {"wav", "flac"} else "wav"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    audio = _np.zeros((n_frames, n_channels), dtype=_np.float32)
    if normalize_output:
        audio = _np.clip(audio, -1.0, 1.0)
    _sf.write(str(output_path), audio, sample_rate, format=output_format.upper())

    return T2MClipResult(
        audio_path=output_path,
        duration_ms=duration_ms,
        used_seed=request.seed,
        backend_name=model_config.name,
        metadata={
            "backend_type": model_config.backend_type,
            "note": "Silent preview clip. Replace t2m_generate_clip with real model.",
            "capability_ready": bool(model_config.extra.get("ready", False)),
            "capability_reason": str(model_config.extra.get("reason", "")),
            "requested_output_format": requested_format,
            "output_format": output_format,
            "normalize_output": normalize_output,
            "output_sample_rate": sample_rate,
        }
    )