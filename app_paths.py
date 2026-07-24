import os
import sys
from pathlib import Path

def _portable_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resolve_echo_root() -> Path:
    override = os.environ.get("ECHO_PRO_HOME", "").strip()
    if override:
        return Path(override)

    portable_marker_dir = _portable_base_dir()
    portable_marker = portable_marker_dir / ".echo_portable"
    if portable_marker.exists():
        return portable_marker_dir / "data"

    return Path(os.environ["APPDATA"]) / "EchoPro"


ECHO_ROOT = resolve_echo_root()
PROJECTS_DIR = ECHO_ROOT / "projects"
VOICES_DIR = ECHO_ROOT / "voices"
GENERATED_DIR = ECHO_ROOT / "generated"
TOOLS_DIR = ECHO_ROOT / "tools"
RUNTIME_DIR = ECHO_ROOT / "runtime"
MODELS_DIR = ECHO_ROOT / "models"
RVC_MODELS_DIR = MODELS_DIR / "rvc"
ACE_MODELS_DIR = MODELS_DIR / "ace_step_1_5"

def ensure_dirs():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    RVC_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    ACE_MODELS_DIR.mkdir(parents=True, exist_ok=True)
