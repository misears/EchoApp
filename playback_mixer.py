import math

import numpy as np
import sounddevice as sd
import soundfile as sf

from project_model import Project

TARGET_SAMPLE_RATE = 44100


def _ms_to_frames(ms: int) -> int:
    return max(0, int(round((float(ms) / 1000.0) * TARGET_SAMPLE_RATE)))


def _db_to_linear(db: float) -> float:
    return float(10.0 ** (float(db) / 20.0))


def _equal_power_pan_gains(pan: float) -> tuple[float, float]:
    clamped_pan = max(-1.0, min(1.0, float(pan)))
    angle = (clamped_pan + 1.0) * (math.pi * 0.25)
    return float(math.cos(angle)), float(math.sin(angle))


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


def _project_duration_ms(project: Project) -> int:
    max_end_ms = 0
    for clip in project.clips:
        end_ms = clip.start_ms + clip.length_ms
        if end_ms > max_end_ms:
            max_end_ms = end_ms
    for track in project.tracks:
        settings = track.playback_settings
        if settings.loop_enabled and settings.loop_end_ms > settings.loop_start_ms:
            loop_length_ms = settings.loop_end_ms - settings.loop_start_ms
            max_end_ms = max(max_end_ms, settings.loop_end_ms + loop_length_ms)
    return max_end_ms


def project_duration_ms(project: Project) -> int:
    return max(0, int(_project_duration_ms(project)))


def _clip_fade_values_ms(clip) -> tuple[int, int]:
    metadata = getattr(clip, "metadata", {}) or {}
    clip_length_ms = max(1, int(getattr(clip, "length_ms", 1)))
    try:
        fade_in_ms = int(metadata.get("fade_in_ms", 0))
    except (TypeError, ValueError):
        fade_in_ms = 0
    try:
        fade_out_ms = int(metadata.get("fade_out_ms", 0))
    except (TypeError, ValueError):
        fade_out_ms = 0
    return max(0, min(clip_length_ms, fade_in_ms)), max(0, min(clip_length_ms, fade_out_ms))


def _apply_clip_fades(audio: np.ndarray, fade_in_ms: int, fade_out_ms: int) -> np.ndarray:
    if audio.shape[0] == 0 or (fade_in_ms <= 0 and fade_out_ms <= 0):
        return audio
    output = np.array(audio, copy=True)
    fade_in_frames = min(_ms_to_frames(fade_in_ms), output.shape[0])
    if fade_in_frames > 1:
        ramp_in = np.linspace(0.0, 1.0, fade_in_frames, endpoint=True, dtype=np.float32)[:, None]
        output[:fade_in_frames, :] *= ramp_in

    fade_out_frames = min(_ms_to_frames(fade_out_ms), output.shape[0])
    if fade_out_frames > 1:
        ramp_out = np.linspace(1.0, 0.0, fade_out_frames, endpoint=True, dtype=np.float32)[:, None]
        output[-fade_out_frames:, :] *= ramp_out
    return output


def _group_clips_by_track(project: Project) -> dict[int, list]:
    grouped: dict[int, list] = {}
    for clip in project.clips:
        grouped.setdefault(int(clip.track_index), []).append(clip)
    return grouped


def _render_track_segment(track_clips: list, total_frames: int) -> np.ndarray:
    track_buffer = np.zeros((max(1, total_frames), 2), dtype=np.float32)
    for clip in track_clips:
        try:
            metadata = getattr(clip, "metadata", {}) or {}
            if metadata.get("source") == "recording_take" and not metadata.get("is_active_take", True):
                continue

            seg = _load_clip_stereo(clip.file_path, TARGET_SAMPLE_RATE)
            max_clip_frames = int(max(1, round((clip.length_ms / 1000.0) * TARGET_SAMPLE_RATE)))
            if seg.shape[0] > max_clip_frames:
                seg = seg[:max_clip_frames, :]

            fade_in_ms, fade_out_ms = _clip_fade_values_ms(clip)
            if fade_in_ms > 0 or fade_out_ms > 0:
                seg = _apply_clip_fades(seg, int(fade_in_ms), int(fade_out_ms))

            start = int(max(0, round((clip.start_ms / 1000.0) * TARGET_SAMPLE_RATE)))
            if start >= track_buffer.shape[0]:
                continue

            end = min(track_buffer.shape[0], start + seg.shape[0])
            frame_count = end - start
            if frame_count <= 0:
                continue

            track_buffer[start:end, :] += seg[:frame_count, :]
        except Exception as e:
            print(f"Error loading clip {clip.file_path}: {e}")
            continue
    return track_buffer


def _apply_loop_region(audio: np.ndarray, loop_enabled: bool, loop_start_ms: int, loop_end_ms: int) -> np.ndarray:
    if not loop_enabled:
        return audio
    loop_start = min(_ms_to_frames(loop_start_ms), max(0, audio.shape[0] - 1))
    loop_end = min(_ms_to_frames(loop_end_ms), audio.shape[0])
    if loop_end - loop_start <= 1:
        return audio
    loop_chunk = audio[loop_start:loop_end, :].copy()
    if loop_chunk.shape[0] == 0:
        return audio
    output = audio.copy()
    write_pos = loop_end
    while write_pos < output.shape[0]:
        take = min(loop_chunk.shape[0], output.shape[0] - write_pos)
        output[write_pos:write_pos + take, :] = loop_chunk[:take, :]
        write_pos += take
    return output


def _apply_fades(audio: np.ndarray, fade_in_ms: int, fade_out_ms: int) -> np.ndarray:
    output = audio.copy()
    fade_in_frames = min(_ms_to_frames(fade_in_ms), output.shape[0])
    if fade_in_frames > 1:
        ramp_in = np.linspace(0.0, 1.0, fade_in_frames, endpoint=True, dtype=np.float32)[:, None]
        output[:fade_in_frames, :] *= ramp_in

    fade_out_frames = min(_ms_to_frames(fade_out_ms), output.shape[0])
    if fade_out_frames > 1:
        ramp_out = np.linspace(1.0, 0.0, fade_out_frames, endpoint=True, dtype=np.float32)[:, None]
        output[-fade_out_frames:, :] *= ramp_out
    return output


def _apply_track_gain_and_pan(audio: np.ndarray, volume_db: float, pan: float) -> np.ndarray:
    if audio.shape[0] == 0:
        return audio
    gain = _db_to_linear(volume_db)
    left_pan, right_pan = _equal_power_pan_gains(pan)
    output = np.array(audio, copy=True)
    output[:, 0] *= float(gain * left_pan)
    output[:, 1] *= float(gain * right_pan)
    return output


def _apply_echo(audio: np.ndarray, delay_ms: int, decay: float, mix: float) -> np.ndarray:
    delay_frames = _ms_to_frames(delay_ms)
    if delay_frames <= 0 or delay_frames >= audio.shape[0] or mix <= 0.0 or decay <= 0.0:
        return audio
    wet = np.zeros_like(audio)
    wet[delay_frames:, :] = audio[:-delay_frames, :] * float(decay)
    return np.clip(audio + (wet * float(mix)), -1.0, 1.0).astype(np.float32)


def _apply_distortion(audio: np.ndarray, drive: float, mix: float) -> np.ndarray:
    if mix <= 0.0 or drive <= 1.0:
        return audio
    normalizer = max(float(np.tanh(drive)), 1e-6)
    processed = np.tanh(audio * float(drive)) / normalizer
    return np.clip((audio * (1.0 - float(mix))) + (processed * float(mix)), -1.0, 1.0).astype(np.float32)


def _apply_chorus(audio: np.ndarray, depth_ms: int, mix: float) -> np.ndarray:
    delay_a = _ms_to_frames(depth_ms)
    delay_b = _ms_to_frames(int(round(depth_ms * 1.6)))
    if mix <= 0.0 or delay_a <= 0 or delay_a >= audio.shape[0]:
        return audio
    wet = np.zeros_like(audio)
    wet[delay_a:, 0] += audio[:-delay_a, 0] * 0.6
    wet[delay_a:, 1] += audio[:-delay_a, 1] * 0.6
    if 0 < delay_b < audio.shape[0]:
        wet[delay_b:, 0] += audio[:-delay_b, 1] * 0.25
        wet[delay_b:, 1] += audio[:-delay_b, 0] * 0.25
    return np.clip(audio + (wet * float(mix)), -1.0, 1.0).astype(np.float32)


def _apply_track_effects(audio: np.ndarray, effects) -> np.ndarray:
    output = audio
    if effects.chorus_enabled:
        output = _apply_chorus(output, int(effects.chorus_depth_ms), float(effects.chorus_mix))
    if effects.echo_enabled:
        output = _apply_echo(output, int(effects.echo_delay_ms), float(effects.echo_decay), float(effects.echo_mix))
    if effects.distortion_enabled:
        output = _apply_distortion(output, float(effects.distortion_drive), float(effects.distortion_mix))
    return output


def _apply_master_limiter(audio: np.ndarray, threshold_db: float) -> np.ndarray:
    threshold_db = max(-24.0, min(0.0, float(threshold_db)))
    threshold_linear = float(10.0 ** (threshold_db / 20.0))
    if threshold_linear <= 0.0:
        return audio

    limited = np.array(audio, copy=True)
    limited = np.clip(limited, -threshold_linear, threshold_linear)
    if threshold_linear < 1.0:
        limited = limited / threshold_linear
    return np.clip(limited, -1.0, 1.0).astype(np.float32)


def mix_project_to_segment(project: Project) -> np.ndarray:
    """
    Mix all tracks in the project into a stereo float32 buffer.
    Returns an array shaped (frames, 2) at TARGET_SAMPLE_RATE.
    """
    if not project.tracks:
        return np.zeros((TARGET_SAMPLE_RATE, 2), dtype=np.float32)

    max_end_ms = _project_duration_ms(project)

    max_end_frames = int(math.ceil(((max_end_ms + 1000) / 1000.0) * TARGET_SAMPLE_RATE))
    master = np.zeros((max(1, max_end_frames), 2), dtype=np.float64)
    any_solo = any(track.soloed for track in project.tracks)
    clips_by_track = _group_clips_by_track(project)

    for track_index, track in enumerate(project.tracks):
        if track.muted:
            continue
        if any_solo and not track.soloed:
            continue

        track_clips = clips_by_track.get(int(track_index), [])
        if not track_clips:
            continue
        track_audio = _render_track_segment(track_clips, master.shape[0])
        settings = track.playback_settings
        track_audio = _apply_loop_region(
            track_audio,
            bool(settings.loop_enabled),
            int(settings.loop_start_ms),
            int(settings.loop_end_ms),
        )
        track_audio = _apply_track_effects(track_audio, settings.effects)
        track_audio = _apply_fades(track_audio, int(settings.fade_in_ms), int(settings.fade_out_ms))
        track_audio = _apply_track_gain_and_pan(track_audio, float(track.volume_db), float(getattr(track, "pan", 0.0)))
        master += track_audio.astype(np.float64, copy=False)

    metadata = project.metadata if isinstance(getattr(project, "metadata", {}), dict) else {}
    limiter_threshold_db = float(metadata.get("master_limiter_threshold_db", -3.0))
    master = _apply_master_limiter(master, limiter_threshold_db)
    return np.clip(master, -1.0, 1.0).astype(np.float32)


def _slice_mix_window(mix: np.ndarray, start_ms: int = 0, end_ms: int | None = None) -> np.ndarray:
    if mix.shape[0] == 0:
        return mix
    start_frame = min(_ms_to_frames(max(0, int(start_ms))), mix.shape[0])
    end_frame = mix.shape[0]
    if end_ms is not None:
        end_frame = min(max(start_frame, _ms_to_frames(max(0, int(end_ms)))), mix.shape[0])
    return mix[start_frame:end_frame, :]


def play_project(project: Project, *, start_ms: int = 0, end_ms: int | None = None, blocking: bool = False) -> int:
    """
    Mix and play the project.
    Returns the duration of the segment submitted for playback in milliseconds.
    """
    mix = mix_project_to_segment(project)
    mix = _slice_mix_window(mix, start_ms=start_ms, end_ms=end_ms)
    if mix.shape[0] == 0:
        return 0
    sd.stop()
    sd.play(mix, samplerate=TARGET_SAMPLE_RATE, blocking=blocking)
    return int(round((float(mix.shape[0]) / float(TARGET_SAMPLE_RATE)) * 1000.0))


def stop_playback() -> None:
    sd.stop()


def is_playback_active() -> bool:
    try:
        stream = sd.get_stream()
    except Exception:
        return False
    return bool(stream is not None and stream.active)