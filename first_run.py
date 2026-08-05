"""First-run detection for Echo Pro.

Writes a sentinel file to ECHO_ROOT on first launch so the app can show
the welcome/setup dialog exactly once.
"""

from pathlib import Path
from app_paths import ECHO_ROOT, ensure_dirs

FIRST_RUN_FLAG = ECHO_ROOT / "first_run_done.txt"

def is_first_run() -> bool:
    ensure_dirs()
    return not FIRST_RUN_FLAG.exists()

def mark_first_run_done():
    ECHO_ROOT.mkdir(parents=True, exist_ok=True)
    FIRST_RUN_FLAG.write_text("done", encoding="utf-8")