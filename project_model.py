## project_model.py

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List
import json
from pathlib import Path

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
    volume_db: float = 0.0  # 0 = original, negative = quieter, positive = louder
    muted: bool = False
    soloed: bool = False

@dataclass
class Project:
    name: str
    tracks: List[Track]
    clips: List[Clip]
    metadata: Dict[str, Any] = field(default_factory=dict)

def new_empty_project(name: str) -> Project:
    return Project(name=name, tracks=[], clips=[])

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
    tracks = [Track(**t) for t in data.get("tracks", [])]
    clips = []
    for clip_data in data.get("clips", []):
        clip_copy = dict(clip_data)
        clip_copy.setdefault("metadata", {})
        clips.append(Clip(**clip_copy))
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return Project(name=data.get("name", "Untitled"), tracks=tracks, clips=clips, metadata=metadata)