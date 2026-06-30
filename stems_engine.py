
import subprocess
import os
from pathlib import Path
import shutil

from project_model import Clip, Track, Project
from audio_info import get_audio_length_ms

def separate_stems(input_path: str, output_dir: Path) -> dict:
    """
    Use Demucs to separate a song into stems.
    Returns a dict mapping stem names to file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "demucs",
        "-o", str(output_dir),
        input_path
    ]
    subprocess.run(cmd, check=True)

    stem_folder = None
    for root, dirs, files in os.walk(output_dir):
        wavs = [f for f in files if f.lower().endswith(".wav")]
        if wavs:
            stem_folder = Path(root)
            break

    if stem_folder is None:
        raise RuntimeError("Could not find stem folder after Demucs run.")

    stems = {}
    for stem_file in stem_folder.glob("*.wav"):
        target = output_dir / stem_file.name
        if target != stem_file:
            shutil.move(str(stem_file), target)
        stem_name = stem_file.stem.lower()
        stems[stem_name] = str(target)

    return stems

def add_stems_to_project(project: Project, stems: dict, project_folder: Path, next_clip_id_start: int = 1):
    """
    Given a project and a dict of stems (name -> path),
    create tracks and clips for each stem.
    Returns updated next_clip_id.
    """
    next_clip_id = next_clip_id_start

    stem_order = ["vocals", "drums", "bass", "guitar", "other"]
    for stem_name in stem_order:
        if stem_name not in stems:
            continue
        file_path = stems[stem_name]

        track_name = stem_name.capitalize()
        track_index = len(project.tracks)
        project.tracks.append(Track(name=track_name))

        length_ms = get_audio_length_ms(file_path)
        clip = Clip(
            id=next_clip_id,
            track_index=track_index,
            file_path=file_path,
            start_ms=0,
            length_ms=length_ms
        )
        project.clips.append(clip)
        next_clip_id += 1

    return next_clip_id