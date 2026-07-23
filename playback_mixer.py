from pathlib import Path
from pydub import AudioSegment
from pydub.playback import play

from project_model import Project

def mix_project_to_segment(project: Project) -> AudioSegment:
    """
    Mix all clips in the project into a single AudioSegment,
    applying track volumes.
    """
    if not project.tracks:
        return AudioSegment.silent(duration=1000)

    max_end_ms = 0
    for clip in project.clips:
        end_ms = clip.start_ms + clip.length_ms
        if end_ms > max_end_ms:
            max_end_ms = end_ms

    master = AudioSegment.silent(duration=max_end_ms + 1000)  # extra second

    track_volumes = {i: t.volume_db for i, t in enumerate(project.tracks)}
    any_solo = any(track.soloed for track in project.tracks)

    for clip in project.clips:
        try:
            track = project.tracks[clip.track_index]
            if track.muted:
                continue
            if any_solo and not track.soloed:
                continue

            seg = AudioSegment.from_file(clip.file_path)
            if len(seg) > clip.length_ms:
                seg = seg[:clip.length_ms]
            db_change = track_volumes.get(clip.track_index, 0.0)
            seg = seg + db_change
            master = master.overlay(seg, position=clip.start_ms)
        except Exception as e:
            print(f"Error loading clip {clip.file_path}: {e}")
            continue

    return master

def play_project(project: Project):
    """
    Mix and play the project.
    """
    mix = mix_project_to_segment(project)
    play(mix)