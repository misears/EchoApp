import os
import sys
from pathlib import Path

def _portable_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _read_home_override_file() -> Path | None:
    override_file = _portable_base_dir() / "echo_home.txt"
    if not override_file.exists():
        return None
    try:
        value = override_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not value:
        return None
    return Path(value).expanduser()


def resolve_echo_root() -> Path:
    override = os.environ.get("ECHO_PRO_HOME", "").strip()
    if override:
        return Path(override)

    file_override = _read_home_override_file()
    if file_override is not None:
        return file_override

    portable_marker_dir = _portable_base_dir()
    portable_marker = portable_marker_dir / ".echo_portable"
    if portable_marker.exists():
        return portable_marker_dir / "data"

    local_app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not local_app_data:
        return Path.home() / "EchoProData"
    return Path(local_app_data) / "EchoProData"


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
