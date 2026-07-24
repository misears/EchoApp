
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


def _migrate_profile(raw_profile: dict) -> VoiceProfile:
    name = str(raw_profile.get("name", "")).strip()
    file_path = str(raw_profile.get("file_path", "")).strip()
    created_at = str(raw_profile.get("created_at", "")).strip() or datetime.now().isoformat()
    consent_flag = bool(raw_profile.get("consent_flag", True))
    source_type = str(raw_profile.get("source_type", "user_recording")).strip() or "user_recording"
    return VoiceProfile(
        name=name,
        file_path=file_path,
        created_at=created_at,
        consent_flag=consent_flag,
        source_type=source_type,
    )

def load_voice_profiles() -> List[VoiceProfile]:
    ensure_dirs()
    if not VOICE_INDEX_FILE.exists():
        return []
    try:
        data = json.loads(VOICE_INDEX_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    raw_profiles = data.get("profiles", [])
    if not isinstance(raw_profiles, list):
        return []

    migrated_profiles: List[VoiceProfile] = []
    for raw_profile in raw_profiles:
        if not isinstance(raw_profile, dict):
            continue
        profile = _migrate_profile(raw_profile)
        if not profile.name or not profile.file_path:
            continue
        if not Path(profile.file_path).exists():
            continue
        migrated_profiles.append(profile)
    return migrated_profiles

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