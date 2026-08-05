"""Project data model for Echo Pro.

Defines the core dataclasses (Project, Track, Clip, TrackPlaybackSettings,
TrackEffectChain) and JSON serialisation helpers (save_project, load_project).
All coercion and schema-migration logic lives here so callers receive clean,
fully-typed objects regardless of the on-disk format version.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List
import json
from pathlib import Path


# ── DATACLASSES ───────────────────────────────────────────────────────────────
@dataclass
class TrackEffectChain:
    echo_enabled: bool = False
    echo_delay_ms: int = 180
    echo_decay: float = 0.35
    echo_mix: float = 0.25
    distortion_enabled: bool = False
    distortion_drive: float = 1.8
    distortion_mix: float = 0.2
    chorus_enabled: bool = False
    chorus_depth_ms: int = 18
    chorus_mix: float = 0.2


@dataclass
class TrackPlaybackSettings:
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    loop_enabled: bool = False
    loop_start_ms: int = 0
    loop_end_ms: int = 0
    effects: TrackEffectChain = field(default_factory=TrackEffectChain)
    active_automation_parameter: str = "volume_db"
    automation: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)


@dataclass
class Clip:
    id: int
    track_index: int
    file_path: str
    start_ms: int   # where clip starts on timeline
    length_ms: int  # how long the clip is
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Track:
    name: str
    track_type: str = "Audio"
    volume_db: float = 0.0  # 0 = original, negative = quieter, positive = louder
    pan: float = 0.0
    muted: bool = False
    soloed: bool = False
    color_hex: str = "#00F0FF"
    input_source: str = "Auto"
    send_a: float = 0.0
    send_b: float = 0.0
    playback_settings: TrackPlaybackSettings = field(default_factory=TrackPlaybackSettings)

@dataclass
class Project:
    name: str
    tracks: List[Track]
    clips: List[Clip]
    metadata: Dict[str, Any] = field(default_factory=dict)

def new_empty_project(name: str) -> Project:
    return Project(name=name, tracks=[], clips=[])


# ── COERCION / SCHEMA-MIGRATION HELPERS ─────────────────────────────
def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_track_effect_chain(data: Any) -> TrackEffectChain:
    if not isinstance(data, dict):
        return TrackEffectChain()
    return TrackEffectChain(
        echo_enabled=bool(data.get("echo_enabled", False)),
        echo_delay_ms=max(0, _coerce_int(data.get("echo_delay_ms", 180), 180)),
        echo_decay=_coerce_float(data.get("echo_decay", 0.35), 0.35),
        echo_mix=_coerce_float(data.get("echo_mix", 0.25), 0.25),
        distortion_enabled=bool(data.get("distortion_enabled", False)),
        distortion_drive=_coerce_float(data.get("distortion_drive", 1.8), 1.8),
        distortion_mix=_coerce_float(data.get("distortion_mix", 0.2), 0.2),
        chorus_enabled=bool(data.get("chorus_enabled", False)),
        chorus_depth_ms=max(0, _coerce_int(data.get("chorus_depth_ms", 18), 18)),
        chorus_mix=_coerce_float(data.get("chorus_mix", 0.2), 0.2),
    )


def _normalize_track_playback_settings(data: Any) -> TrackPlaybackSettings:
    if not isinstance(data, dict):
        return TrackPlaybackSettings()
    automation_data = data.get("automation", {})
    normalized_automation: Dict[str, List[Dict[str, Any]]] = {}
    if isinstance(automation_data, dict):
        for parameter_name, points in automation_data.items():
            if not isinstance(points, list):
                continue
            sanitized_points: List[Dict[str, Any]] = []
            for point in points:
                if not isinstance(point, dict):
                    continue
                time_ms = max(0, _coerce_int(point.get("time_ms", 0), 0))
                value = max(0.0, min(1.0, _coerce_float(point.get("value", 0.5), 0.5)))
                sanitized_points.append({"time_ms": time_ms, "value": value})
            if sanitized_points:
                sanitized_points.sort(key=lambda item: int(item["time_ms"]))
                normalized_automation[str(parameter_name)] = sanitized_points
    active_automation_parameter = str(data.get("active_automation_parameter", "volume_db") or "volume_db").strip().lower()
    if active_automation_parameter not in {"volume_db", "pan", "send_a", "send_b"}:
        active_automation_parameter = "volume_db"
    return TrackPlaybackSettings(
        fade_in_ms=max(0, _coerce_int(data.get("fade_in_ms", 0), 0)),
        fade_out_ms=max(0, _coerce_int(data.get("fade_out_ms", 0), 0)),
        loop_enabled=bool(data.get("loop_enabled", False)),
        loop_start_ms=max(0, _coerce_int(data.get("loop_start_ms", 0), 0)),
        loop_end_ms=max(0, _coerce_int(data.get("loop_end_ms", 0), 0)),
        effects=_normalize_track_effect_chain(data.get("effects", {})),
        active_automation_parameter=active_automation_parameter,
        automation=normalized_automation,
    )


def _track_from_dict(track_data: Dict[str, Any]) -> Track:
    track_copy = dict(track_data)
    track_type = str(track_copy.get("track_type", "Audio") or "Audio").strip()
    if track_type not in {"Audio", "AI Stem", "MIDI", "Bus"}:
        track_type = "Audio"
    track_copy["track_type"] = track_type
    track_copy["playback_settings"] = _normalize_track_playback_settings(track_copy.get("playback_settings", {}))
    return Track(**track_copy)


def save_project(project: Project, path: Path):
    data = {
        "name": project.name,
        "tracks": [asdict(t) for t in project.tracks],
        "clips": [asdict(c) for c in project.clips],
        "metadata": project.metadata,
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def load_project(path: Path) -> Project:
    data = json.loads(path.read_text(encoding="utf-8"))
    tracks = [_track_from_dict(t) for t in data.get("tracks", [])]
    clips = []
    for clip_data in data.get("clips", []):
        clip_copy = dict(clip_data)
        clip_copy.setdefault("metadata", {})
        clips.append(Clip(**clip_copy))
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return Project(name=data.get("name", "Untitled"), tracks=tracks, clips=clips, metadata=metadata)