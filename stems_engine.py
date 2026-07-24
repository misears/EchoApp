
import subprocess
import os
from pathlib import Path
import shutil
import time
from typing import Callable, Optional

from project_model import Clip, Track, Project
from audio_info import get_audio_length_ms


class StemSeparationError(RuntimeError):
    pass


class StemDependencyError(StemSeparationError):
    pass


class StemCancelledError(StemSeparationError):
    pass


def _normalize_failure(stderr_text: str) -> StemSeparationError:
    lowered = stderr_text.lower()
    if "ffmpeg" in lowered and ("not found" in lowered or "missing" in lowered):
        return StemDependencyError(
            "ffmpeg is missing. Run install_echo_pro.bat install (or update) to install local ffmpeg tooling."
        )
    if "demucs" in lowered and ("not found" in lowered or "no module named" in lowered):
        return StemDependencyError(
            "Demucs runtime is missing. Run install_echo_pro.bat install (or update) to install local demucs tooling."
        )
    return StemSeparationError(stderr_text.strip() or "Demucs failed while splitting stems.")


def separate_stems(
    input_path: str,
    output_dir: Path,
    *,
    demucs_executable: str = "demucs",
    ffmpeg_executable: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> dict:
    """
    Use Demucs to separate a song into stems.
    Returns a dict mapping stem names to file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [demucs_executable, "-o", str(output_dir), input_path]
    env = os.environ.copy()
    if ffmpeg_executable:
        env["FFMPEG_BINARY"] = ffmpeg_executable

    if progress_callback is not None:
        progress_callback("Starting Demucs separation...")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
    except FileNotFoundError as exc:
        raise StemDependencyError(
            "Demucs executable was not found. Run install_echo_pro.bat install (or update)."
        ) from exc

    stderr_chunks = []
    while process.poll() is None:
        if cancel_check is not None and cancel_check():
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            raise StemCancelledError("Stem separation was cancelled.")
        if progress_callback is not None:
            progress_callback("Demucs processing in progress...")
        time.sleep(0.2)

    stdout_data, stderr_data = process.communicate()
    if stdout_data:
        stderr_chunks.append(stdout_data)
    if stderr_data:
        stderr_chunks.append(stderr_data)
    stderr_text = "\n".join(stderr_chunks)

    if process.returncode != 0:
        raise _normalize_failure(stderr_text)

    stem_folder = None
    for root, dirs, files in os.walk(output_dir):
        wavs = [f for f in files if f.lower().endswith(".wav")]
        if wavs:
            stem_folder = Path(root)
            break

    if stem_folder is None:
        raise StemSeparationError("Could not find stem folder after Demucs run.")

    stems = {}
    for stem_file in stem_folder.glob("*.wav"):
        target = output_dir / stem_file.name
        if target != stem_file:
            shutil.move(str(stem_file), target)
        stem_name = stem_file.stem.lower()
        stems[stem_name] = str(target)

    return stems

# Preferred display order for well-known demucs stem names
_STEM_ORDER = ["vocals", "drums", "bass", "guitar", "piano", "other"]


def add_stems_to_project(
    project: Project,
    stems: dict,
    project_folder: Path,
    next_clip_id_start: int = 1,
) -> int:
    """Given a project and a dict of stems (name -> path),
    create tracks and clips for each stem.
    Returns updated next_clip_id.

    Stems are added in the preferred order first, then any
    additional stems not in the preferred list are appended.
    """
    next_clip_id = next_clip_id_start

    # Ordered stems first, then any extras (e.g. from 6-source model)
    ordered = [s for s in _STEM_ORDER if s in stems]
    extras = [s for s in stems if s not in _STEM_ORDER]
    all_stems = ordered + extras

    for stem_name in all_stems:
        file_path = stems[stem_name]

        if not Path(file_path).exists():
            continue  # skip missing files gracefully

        try:
            length_ms = get_audio_length_ms(file_path)
        except Exception:
            length_ms = 0  # add track even if duration unknown

        track_name = stem_name.capitalize()
        track_index = len(project.tracks)
        project.tracks.append(Track(name=track_name))

        clip = Clip(
            id=next_clip_id,
            track_index=track_index,
            file_path=file_path,
            start_ms=0,
            length_ms=length_ms,
        )
        project.clips.append(clip)
        next_clip_id += 1

    return next_clip_id