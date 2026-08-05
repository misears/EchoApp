"""Stem separation engine for Echo Pro.

Wraps Demucs to split an audio file into stems (vocals, drums, bass, other).
Resolves the Demucs executable and FFmpeg from the runtime venv or PATH,
streams progress to an optional callback, and supports cancellation.
Results are added directly to the current project as new tracks.
"""

import os
import queue
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import soundfile as sf

from app_paths import MODELS_DIR, RUNTIME_DIR, TOOLS_DIR
from project_model import Clip, Track, Project
from audio_info import get_audio_length_ms


class StemSeparationError(RuntimeError):
    pass


class StemDependencyError(StemSeparationError):
    pass


class StemCancelledError(StemSeparationError):
    pass


DEFAULT_DEMUCS_MODEL = "htdemucs"
DEMUCS_MODEL_OPTIONS: tuple[tuple[str, str], ...] = (
    ("htdemucs", "Balanced 4-stem"),
    ("htdemucs_ft", "Fine-tuned 4-stem"),
    ("htdemucs_6s", "6-stem (adds guitar/piano)"),
)

_DEMUCS_PROGRESS_PERCENT = re.compile(r"(?P<pct>\d{1,3})%\|")


@dataclass(frozen=True)
class StemRuntimeConfig:
    demucs_executable: str
    demucs_repo: Optional[str]
    ffmpeg_executable: Optional[str]


def resolve_stem_runtime() -> StemRuntimeConfig:
    app_root = Path(__file__).resolve().parent
    local_demucs = RUNTIME_DIR / "venv" / "Scripts" / "demucs.exe"
    local_demucs_repo = MODELS_DIR / "demucs" / "repo"
    local_ffmpeg = TOOLS_DIR / "ffmpeg" / "current" / "bin" / "ffmpeg.exe"
    seed_ffmpeg = app_root / "seeds" / "FFmpeg-master" / "bin" / "ffmpeg.exe"

    if local_demucs.exists():
        demucs_executable = str(local_demucs)
    else:
        demucs_executable = shutil.which("demucs") or "demucs"

    if local_ffmpeg.exists():
        ffmpeg_executable = str(local_ffmpeg)
    elif seed_ffmpeg.exists():
        ffmpeg_executable = str(seed_ffmpeg)
    else:
        ffmpeg_executable = shutil.which("ffmpeg")

    demucs_repo = str(local_demucs_repo) if local_demucs_repo.exists() else None
    return StemRuntimeConfig(
        demucs_executable=demucs_executable,
        demucs_repo=demucs_repo,
        ffmpeg_executable=ffmpeg_executable,
    )


def get_stem_backend_capability() -> dict:
    runtime = resolve_stem_runtime()
    demucs_ready = Path(runtime.demucs_executable).exists() or shutil.which(runtime.demucs_executable) is not None
    ffmpeg_ready = bool(runtime.ffmpeg_executable) and (
        Path(runtime.ffmpeg_executable).exists() or shutil.which(runtime.ffmpeg_executable) is not None
    )

    if not demucs_ready:
        reason = "Demucs runtime is not installed yet. Run install_echo_pro.bat install/update."
    elif not ffmpeg_ready:
        reason = "ffmpeg is not available yet. Run install_echo_pro.bat install/update."
    else:
        reason = ""

    return {
        "backend": "Demucs",
        "ready": demucs_ready and ffmpeg_ready,
        "reason": reason,
        "demucs_executable": runtime.demucs_executable,
        "demucs_repo": runtime.demucs_repo,
        "ffmpeg_executable": runtime.ffmpeg_executable or "",
    }


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
    if "assertionerror" in lowered or "pad1d" in lowered:
        return StemSeparationError(
            "Demucs could not process the source audio as-is. Try a longer source file or update the stem preflight handling."
        )
    return StemSeparationError(stderr_text.strip() or "Demucs failed while splitting stems.")


def _prepare_demucs_input(input_path: Path, *, minimum_seconds: float = 10.0) -> tuple[Path, int]:
    """Pad very short audio so Demucs receives a stable minimum input length."""
    original_length_ms = get_audio_length_ms(str(input_path))
    if original_length_ms >= int(minimum_seconds * 1000):
        return input_path, original_length_ms

    try:
        audio, sample_rate = sf.read(str(input_path), always_2d=True)
    except Exception:
        return input_path, original_length_ms

    min_frames = int(round(sample_rate * minimum_seconds))
    original_frames = int(audio.shape[0])
    if original_frames >= min_frames:
        return input_path, original_length_ms

    padded = input_path.parent / f"{input_path.stem}_demucs_padded.wav"
    silence_frames = min_frames - original_frames
    padded_audio = np.vstack([audio, np.zeros((silence_frames, audio.shape[1]), dtype=audio.dtype)])
    sf.write(str(padded), padded_audio, sample_rate)
    return padded, original_length_ms


def _trim_audio_file(path: Path, max_frames: int) -> None:
    try:
        audio, sample_rate = sf.read(str(path), always_2d=True)
    except Exception:
        return

    if int(audio.shape[0]) <= int(max_frames):
        return

    trimmed = audio[: int(max_frames)]
    sf.write(str(path), trimmed, sample_rate)


def _format_progress_message(raw_text: str, *, model_name: str, source_name: str) -> str:
    text = raw_text.strip()
    if not text:
        return ""
    lowered = text.lower()

    percent_match = _DEMUCS_PROGRESS_PERCENT.search(text)
    if percent_match:
        return f"Demucs processing {percent_match.group('pct')}% ({model_name})..."
    if "downloading" in lowered:
        return f"Downloading Demucs assets for {model_name}..."
    if "separating track" in lowered:
        return f"Separating {source_name} with {model_name}..."
    if "separated tracks will be stored in" in lowered:
        return "Preparing output folder for stem files..."
    if "selected model is" in lowered:
        return text
    if "model" in lowered and ("htdemucs" in lowered or "mdx" in lowered):
        return f"Using Demucs model {model_name}..."
    if "cpu" in lowered or "cuda" in lowered or "mps" in lowered:
        return f"Demucs backend: {text}"
    return f"Demucs: {text}"


def separate_stems(
    input_path: str,
    output_dir: Path,
    *,
    demucs_executable: str = "demucs",
    demucs_repo: Optional[str] = None,
    ffmpeg_executable: Optional[str] = None,
    demucs_model: str = DEFAULT_DEMUCS_MODEL,
    progress_callback: Optional[Callable[[str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> dict:
    """
    Use Demucs to separate a song into stems.
    Returns a dict mapping stem names to file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    input_file = Path(input_path)
    demucs_input, original_length_ms = _prepare_demucs_input(input_file)

    cmd = [demucs_executable]
    if demucs_repo:
        cmd.extend(["--repo", demucs_repo])
    if demucs_model:
        cmd.extend(["-n", demucs_model])
    cmd.extend(["-o", str(output_dir), str(demucs_input)])
    env = os.environ.copy()
    if ffmpeg_executable:
        env["FFMPEG_BINARY"] = ffmpeg_executable

    if progress_callback is not None:
        progress_callback(f"Starting Demucs separation ({demucs_model})...")
        progress_callback(f"Launching Demucs for {input_file.name}...")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            bufsize=1,
        )
    except FileNotFoundError as exc:
        raise StemDependencyError(
            "Demucs executable was not found. Run install_echo_pro.bat install (or update)."
        ) from exc

    output_chunks: list[str] = []
    output_queue: queue.Queue[str] = queue.Queue()

    def _pump_output(pipe) -> None:
        if pipe is None:
            return
        try:
            for line in iter(pipe.readline, ""):
                output_queue.put(line)
        finally:
            pipe.close()

    output_thread = threading.Thread(target=_pump_output, args=(process.stdout,), daemon=True)
    output_thread.start()

    source_name = input_file.name
    last_status_at = 0.0
    started_at = time.monotonic()
    last_output_message = ""
    while process.poll() is None or not output_queue.empty():
        if cancel_check is not None and cancel_check():
            if progress_callback is not None:
                progress_callback("Cancelling Demucs separation...")
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            raise StemCancelledError("Stem separation was cancelled.")

        saw_output = False
        while True:
            try:
                line = output_queue.get_nowait()
            except queue.Empty:
                break
            saw_output = True
            text = line.strip()
            if not text:
                continue
            output_chunks.append(text)
            if progress_callback is not None:
                message = _format_progress_message(text, model_name=demucs_model, source_name=source_name)
                if message:
                    progress_callback(message)
                    last_output_message = message

        if not saw_output and progress_callback is not None:
            now = time.monotonic()
            if now - last_status_at >= 1.5:
                elapsed_seconds = int(now - started_at)
                if last_output_message:
                    progress_callback(
                        f"Demucs processing... {elapsed_seconds}s elapsed. Last update: {last_output_message}"
                    )
                else:
                    progress_callback(f"Demucs processing... {elapsed_seconds}s elapsed.")
                last_status_at = now
        time.sleep(0.2)

    output_thread.join(timeout=1.0)
    while True:
        try:
            line = output_queue.get_nowait()
        except queue.Empty:
            break
        text = line.strip()
        if text:
            output_chunks.append(text)
            if progress_callback is not None:
                message = _format_progress_message(text, model_name=demucs_model, source_name=source_name)
                if message:
                    progress_callback(message)

    stderr_text = "\n".join(output_chunks)

    if process.returncode != 0:
        raise _normalize_failure(stderr_text)

    if progress_callback is not None:
        progress_callback("Collecting separated stem files...")

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

    if demucs_input != input_file:
        try:
            original_audio, _original_sample_rate = sf.read(str(input_file), always_2d=True)
            original_frames = int(original_audio.shape[0])
            for stem_path in stems.values():
                _trim_audio_file(Path(stem_path), original_frames)
        finally:
            try:
                demucs_input.unlink(missing_ok=True)
            except Exception:
                pass

    if progress_callback is not None:
        progress_callback(f"Demucs finished. {len(stems)} stems ready.")

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