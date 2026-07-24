import math

import numpy as np
import sounddevice as sd
import soundfile as sf

from project_model import Project

TARGET_SAMPLE_RATE = 44100


def _resample_stereo(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Resample stereo float audio from src_rate to dst_rate using linear interpolation."""
    if src_rate == dst_rate or audio.shape[0] == 0:
        return audio

    src_len = int(audio.shape[0])
    dst_len = max(1, int(round(src_len * float(dst_rate) / float(src_rate))))
    src_x = np.linspace(0.0, 1.0, src_len, endpoint=False, dtype=np.float64)
    dst_x = np.linspace(0.0, 1.0, dst_len, endpoint=False, dtype=np.float64)

    left = np.interp(dst_x, src_x, audio[:, 0])
    right = np.interp(dst_x, src_x, audio[:, 1])
    return np.column_stack((left, right)).astype(np.float32)


def _load_clip_stereo(path: str, target_sample_rate: int) -> np.ndarray:
    """Load one clip as stereo float32 at the requested sample rate."""
    samples, sample_rate = sf.read(path, dtype="float32", always_2d=True)

    if samples.shape[1] == 1:
        samples = np.repeat(samples, 2, axis=1)
    elif samples.shape[1] > 2:
        samples = samples[:, :2]

    return _resample_stereo(samples, int(sample_rate), int(target_sample_rate))


def mix_project_to_segment(project: Project) -> np.ndarray:
    """
    Mix all clips in the project into a stereo float32 buffer.
    Returns an array shaped (frames, 2) at TARGET_SAMPLE_RATE.
    """
    if not project.tracks:
        return np.zeros((TARGET_SAMPLE_RATE, 2), dtype=np.float32)

    max_end_ms = 0
    for clip in project.clips:
        end_ms = clip.start_ms + clip.length_ms
        if end_ms > max_end_ms:
            max_end_ms = end_ms

    max_end_frames = int(math.ceil(((max_end_ms + 1000) / 1000.0) * TARGET_SAMPLE_RATE))
    master = np.zeros((max(1, max_end_frames), 2), dtype=np.float32)

    track_volumes = {i: t.volume_db for i, t in enumerate(project.tracks)}
    any_solo = any(track.soloed for track in project.tracks)

    for clip in project.clips:
        try:
            metadata = getattr(clip, "metadata", {}) or {}
            if metadata.get("source") == "recording_take" and not metadata.get("is_active_take", True):
                continue

            track = project.tracks[clip.track_index]
            if track.muted:
                continue
            if any_solo and not track.soloed:
                continue

            seg = _load_clip_stereo(clip.file_path, TARGET_SAMPLE_RATE)
            max_clip_frames = int(max(1, round((clip.length_ms / 1000.0) * TARGET_SAMPLE_RATE)))
            if seg.shape[0] > max_clip_frames:
                seg = seg[:max_clip_frames, :]

            gain = float(10.0 ** (track_volumes.get(clip.track_index, 0.0) / 20.0))
            seg = seg * gain

            start = int(max(0, round((clip.start_ms / 1000.0) * TARGET_SAMPLE_RATE)))
            if start >= master.shape[0]:
                continue

            end = min(master.shape[0], start + seg.shape[0])
            frame_count = end - start
            if frame_count <= 0:
                continue

            master[start:end, :] += seg[:frame_count, :]
        except Exception as e:
            print(f"Error loading clip {clip.file_path}: {e}")
            continue

    return np.clip(master, -1.0, 1.0).astype(np.float32)

def play_project(project: Project):
    """
    Mix and play the project.
    """
    mix = mix_project_to_segment(project)
    if mix.shape[0] == 0:
        return
    sd.play(mix, samplerate=TARGET_SAMPLE_RATE, blocking=True)