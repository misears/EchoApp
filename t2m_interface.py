
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
    from pydub import AudioSegment

    duration_ms = request.duration_seconds * 1000
    silence = AudioSegment.silent(duration=duration_ms)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    silence.export(str(output_path), format="wav")

    return T2MClipResult(
        audio_path=output_path,
        duration_ms=duration_ms,
        used_seed=request.seed,
        backend_name=model_config.name,
        metadata={
            "backend_type": model_config.backend_type,
            "note": "Placeholder silent clip. Replace t2m_generate_clip with real model."
        }
    )