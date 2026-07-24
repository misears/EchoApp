
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
    Placeholder implementation: generates silence.
    Replace this body with a real T2M model.
    """
    import wave as _wave

    duration_ms = request.duration_seconds * 1000
    sample_rate = model_config.sample_rate
    n_channels = 2 if model_config.stereo else 1
    n_frames = int(sample_rate * request.duration_seconds)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with _wave.open(str(output_path), "w") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(2)        # 16-bit PCM
        wf.setframerate(sample_rate)
        # Write silence: all-zero bytes (n_frames × channels × 2 bytes)
        wf.writeframes(b"\x00" * n_frames * n_channels * 2)

    return T2MClipResult(
        audio_path=output_path,
        duration_ms=duration_ms,
        used_seed=request.seed,
        backend_name=model_config.name,
        metadata={
            "backend_type": model_config.backend_type,
            "note": "Placeholder silent clip. Replace t2m_generate_clip with real model.",
            "capability_ready": bool(model_config.extra.get("ready", False)),
            "capability_reason": str(model_config.extra.get("reason", "")),
        }
    )