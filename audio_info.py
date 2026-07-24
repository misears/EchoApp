import json
import subprocess
from pathlib import Path

import soundfile as sf

# Formats soundfile can read natively (no ffprobe needed)
_SF_FORMATS = {".wav", ".flac", ".ogg", ".aif", ".aiff", ".rf64"}


def get_audio_length_ms(path: str) -> int:
    """Return the length of an audio file in milliseconds.

    Uses soundfile for WAV/FLAC/OGG and ffprobe for everything else
    (e.g. MP3). Raises RuntimeError if neither can determine the length.
    """
    suffix = Path(path).suffix.lower()

    if suffix in _SF_FORMATS:
        try:
            info = sf.info(path)
            return int(info.duration * 1000)
        except Exception:
            pass  # fall through to ffprobe

    # ffprobe handles MP3, AAC, M4A, and any other container
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                path,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        duration_sec = float(data["format"]["duration"])
        return int(duration_sec * 1000)
    except Exception as exc:
        raise RuntimeError(
            f"Could not determine audio length for '{path}'. "
            "Make sure ffprobe (FFmpeg) is installed and on PATH.\n"
            f"Detail: {exc}"
        ) from exc