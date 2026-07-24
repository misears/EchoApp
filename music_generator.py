
import os
from pathlib import Path
from typing import Optional

from t2m_interface import (
    T2MModelConfig,
    T2MClipRequest,
    t2m_generate_clip,
    T2MClipResult,
)
from app_paths import ACE_MODELS_DIR, ECHO_ROOT, ensure_dirs

VALID_STYLES = ["lofi", "rock", "pop", "edm", "orchestral", "jazz", "hiphop", "ambient"]

def get_music_backend_capability() -> dict:
    ensure_dirs()
    configured_model = os.environ.get("ECHO_ACE_MODEL_PATH", "").strip()
    model_path = Path(configured_model) if configured_model else ACE_MODELS_DIR / "current"
    ready = model_path.exists()
    return {
        "backend": "ACE Step 1.5",
        "model_path": str(model_path),
        "ready": ready,
        "reason": "" if ready else "ACE Step 1.5 assets not installed yet. Run install_echo_pro.bat install/update.",
    }

def get_default_t2m_config(use_cloud: bool = False) -> T2MModelConfig:
    capability = get_music_backend_capability()
    backend_type = "cloud" if use_cloud else "offline"
    return T2MModelConfig(
        name="ACE Step 1.5" if not use_cloud else "ACE Step 1.5 (Cloud)",
        backend_type=backend_type,
        max_clip_seconds=30,
        sample_rate=44100,
        stereo=True,
        fp16=True,
        batch_size=1,
        extra={
            "ready": capability["ready"],
            "reason": capability["reason"],
            "model_path": capability["model_path"],
        }
    )

def generate_music_clip(
    style: str,
    genre: str,
    mood: str,
    lyrics: str,
    duration_seconds: int,
    key: str = "",
    chords: str = "",
    time_signature: str = "4/4",
    tempo_bpm: int = 120,
    section_name: str = "",
    seed: Optional[int] = None,
    project_id: str = "default_project",
    use_cloud: bool = False,
) -> T2MClipResult:
    ensure_dirs()
    out_dir = ECHO_ROOT / "generated" / project_id
    out_dir.mkdir(parents=True, exist_ok=True)

    output_path = out_dir / f"{section_name or 'clip'}_{seed or 'x'}.wav"

    prompt_style = style if style in VALID_STYLES else "custom"

    request = T2MClipRequest(
        prompt_style=prompt_style,
        prompt_genre=genre,
        prompt_mood=mood,
        lyrics=lyrics,
        vocal_mode="lead" if lyrics.strip() else "none",
        key=key,
        chords=chords,
        time_signature=time_signature,
        tempo_bpm=tempo_bpm,
        duration_seconds=duration_seconds,
        seed=seed,
        section_name=section_name,
        notes=""
    )

    config = get_default_t2m_config(use_cloud=use_cloud)
    result = t2m_generate_clip(request, output_path, config)
    return result