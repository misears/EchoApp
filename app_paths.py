import os
from pathlib import Path

ECHO_ROOT = Path(os.environ["APPDATA"]) / "EchoPro"
PROJECTS_DIR = ECHO_ROOT / "projects"
VOICES_DIR = ECHO_ROOT / "voices"
GENERATED_DIR = ECHO_ROOT / "generated"

def ensure_dirs():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
