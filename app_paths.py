"""Runtime path resolution for Echo Pro.

Resolves the data root (ECHO_ROOT) in three priority tiers:
  1. ECHO_PRO_HOME environment variable (explicit override)
  2. echo_home.txt file next to the executable (portable override)
  3. A .echo_portable marker file (portable mode) or %LOCALAPPDATA%/EchoProData (installed mode)

All other path constants derive from ECHO_ROOT.
"""

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


# ── MODULE-LEVEL CONSTANTS ────────────────────────────────────────────────────
# Resolved once at import time; all other modules import from here.
ECHO_ROOT = resolve_echo_root()
PROJECTS_DIR = ECHO_ROOT / "projects"
VOICES_DIR = ECHO_ROOT / "voices"
GENERATED_DIR = ECHO_ROOT / "generated"
TOOLS_DIR = ECHO_ROOT / "tools"
RUNTIME_DIR = ECHO_ROOT / "runtime"
MODELS_DIR = ECHO_ROOT / "models"
RVC_MODELS_DIR = MODELS_DIR / "rvc"          # RVC voice-conversion model assets
ACE_MODELS_DIR = MODELS_DIR / "ace_step_1_5" # ACE-Step 1.5 music-generation assets

# ── DIRECTORY BOOTSTRAP ───────────────────────────────────────────────────────
def ensure_dirs():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    RVC_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    ACE_MODELS_DIR.mkdir(parents=True, exist_ok=True)
