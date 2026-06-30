
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List

from app_paths import VOICES_DIR, ensure_dirs

VOICE_INDEX_FILE = VOICES_DIR / "voice_profiles.json"

@dataclass
class VoiceProfile:
    name: str
    file_path: str           # path to reference WAV
    created_at: str
    consent_flag: bool = True
    source_type: str = "user_recording"

def load_voice_profiles() -> List[VoiceProfile]:
    ensure_dirs()
    if not VOICE_INDEX_FILE.exists():
        return []
    data = json.loads(VOICE_INDEX_FILE.read_text(encoding="utf-8"))
    return [VoiceProfile(**vp) for vp in data.get("profiles", [])]

def save_voice_profiles(profiles: List[VoiceProfile]):
    ensure_dirs()
    data = {"profiles": [asdict(p) for p in profiles]}
    VOICE_INDEX_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def add_voice_profile(name: str, wav_path: Path) -> VoiceProfile:
    profiles = load_voice_profiles()
    profile = VoiceProfile(
        name=name,
        file_path=str(wav_path),
        created_at=datetime.now().isoformat(),
        consent_flag=True,
        source_type="user_recording"
    )
    profiles.append(profile)
    save_voice_profiles(profiles)
    return profile