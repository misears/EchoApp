"""
Echo Pro Recording Session — Session management for multi-track recording.
Handles recording state, undo/redo, take management, and recording presets.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from app_paths import ECHO_ROOT
from audio_engine import Track

@dataclass
class RecordingTake:
    """Represents a single recording take."""
    take_number: int
    timestamp: str  # ISO format
    track_id: int
    duration_seconds: float
    start_sample: int = 0
    end_sample: int = 0
    level_stats: Dict[str, float] = field(default_factory=dict)  # min, max, rms
    notes: str = ""
    used: bool = True  # Is this take active?
    is_keeper: bool = False
    is_muted: bool = False
    rating: int = 0
    clip_events: int = 0

@dataclass
class RecordingPreset:
    """Recording configuration preset."""
    name: str
    input_device: Optional[int] = None
    num_tracks: int = 4
    sample_rate: int = 44100
    buffer_size: int = 256
    gain_db: float = 0.0
    auto_gain: bool = False
    click_enabled: bool = True
    click_volume_db: float = -12.0
    metronome_bpm: int = 120
    auto_punch_enabled: bool = False
    auto_punch_start_bars: int = 0
    auto_punch_duration_bars: int = 4


@dataclass
class CompRegion:
    """Non-destructive comp region mapping to a source take."""
    region_id: int
    track_id: int
    start_ms: int
    end_ms: int
    source_take_number: int
    enabled: bool = True

class RecordingSession:
    """Manages a recording session with multiple takes per track."""
    
    def __init__(self, session_id: str, project_name: str):
        self.session_id = session_id
        self.project_name = project_name
        self.created_at = datetime.now().isoformat()
        
        # Takes per track
        self.takes: Dict[int, List[RecordingTake]] = {}
        self.current_take_number: Dict[int, int] = {}
        
        # Settings
        self.preset = RecordingPreset(name="Default", num_tracks=4)
        self.ui_preferences: Dict[str, object] = {
            "take_filter": "all",
            "take_sort": "newest",
            "take_loop": False,
            "hide_inactive_take_clips": False,
        }
        self.comp_regions: Dict[int, List[CompRegion]] = {}
        self.next_comp_region_id: int = 1
        
        # Undo/Redo
        self.undo_stack: List[RecordingTake] = []
        self.redo_stack: List[RecordingTake] = []
        self.max_undo_levels = 10
        
        # Session stats
        self.total_recording_time_seconds = 0.0
        self.total_takes = 0
        
        self._recording_sessions_dir = ECHO_ROOT / "recording_sessions"
        self._recording_sessions_dir.mkdir(exist_ok=True)
    
    def initialize_tracks(self, num_tracks: int) -> None:
        """Initialize takes tracking for N tracks."""
        for track_id in range(num_tracks):
            self.takes[track_id] = []
            self.current_take_number[track_id] = 1

    def ensure_track(self, track_id: int) -> None:
        """Ensure a track has recording state without clearing existing takes."""
        if track_id not in self.takes:
            self.takes[track_id] = []
        if track_id not in self.current_take_number:
            self.current_take_number[track_id] = 1
        if track_id not in self.comp_regions:
            self.comp_regions[track_id] = []

    def get_comp_regions_for_track(self, track_id: int) -> List[CompRegion]:
        """Get non-destructive comp regions for one track."""
        return sorted(self.comp_regions.get(int(track_id), []), key=lambda r: (r.start_ms, r.region_id))

    def create_comp_region(self, track_id: int, start_ms: int, end_ms: int, source_take_number: int) -> Optional[CompRegion]:
        """Create a comp region pointing at a source take."""
        track_id = int(track_id)
        start_ms = int(start_ms)
        end_ms = int(end_ms)
        source_take_number = int(source_take_number)
        if end_ms <= start_ms:
            return None
        if self.get_take(track_id, source_take_number) is None:
            return None

        self.ensure_track(track_id)
        region = CompRegion(
            region_id=self.next_comp_region_id,
            track_id=track_id,
            start_ms=start_ms,
            end_ms=end_ms,
            source_take_number=source_take_number,
            enabled=True,
        )
        self.next_comp_region_id += 1
        self.comp_regions[track_id].append(region)
        return region

    def assign_comp_region_take(self, track_id: int, region_id: int, source_take_number: int) -> bool:
        """Re-assign an existing comp region to another take."""
        track_id = int(track_id)
        region_id = int(region_id)
        source_take_number = int(source_take_number)
        if self.get_take(track_id, source_take_number) is None:
            return False

        for region in self.comp_regions.get(track_id, []):
            if int(region.region_id) == region_id:
                region.source_take_number = source_take_number
                region.enabled = True
                return True
        return False

    def clear_comp_region(self, track_id: int, region_id: int) -> bool:
        """Disable one comp region without deleting source takes."""
        track_id = int(track_id)
        region_id = int(region_id)
        for region in self.comp_regions.get(track_id, []):
            if int(region.region_id) == region_id:
                region.enabled = False
                return True
        return False

    def export_snapshot_payload(self) -> Dict[str, object]:
        """Export session state used by recovery snapshots."""
        payload: Dict[str, object] = {
            "session_id": self.session_id,
            "project_name": self.project_name,
            "created_at": self.created_at,
            "total_takes": int(self.total_takes),
            "total_recording_time_seconds": float(self.total_recording_time_seconds),
            "current_take_number": {str(track_id): int(next_take) for track_id, next_take in self.current_take_number.items()},
            "ui_preferences": dict(self.ui_preferences),
            "takes": {},
            "comp_regions": {},
            "next_comp_region_id": int(self.next_comp_region_id),
        }

        for track_id, takes in self.takes.items():
            payload["takes"][str(track_id)] = [asdict(take) for take in takes]

        for track_id, regions in self.comp_regions.items():
            payload["comp_regions"][str(track_id)] = [asdict(region) for region in regions]

        return payload

    def restore_from_snapshot_payload(self, payload: Dict[str, object]) -> bool:
        """Restore session state from a validated recovery snapshot payload."""
        try:
            self.project_name = str(payload.get("project_name", self.project_name))
            self.total_takes = int(payload.get("total_takes", 0))
            self.total_recording_time_seconds = float(payload.get("total_recording_time_seconds", 0.0))

            self.ui_preferences = dict(payload.get("ui_preferences", self.ui_preferences))

            takes: Dict[int, List[RecordingTake]] = {}
            for track_id_str, takes_data in dict(payload.get("takes", {})).items():
                track_id = int(track_id_str)
                takes[track_id] = [RecordingTake(**take_data) for take_data in takes_data]
            self.takes = takes

            restored_next_take: Dict[int, int] = {}
            for track_id_str, next_take_number in dict(payload.get("current_take_number", {})).items():
                restored_next_take[int(track_id_str)] = int(next_take_number)

            for track_id, take_list in self.takes.items():
                if track_id not in restored_next_take:
                    max_take = max((int(t.take_number) for t in take_list), default=0)
                    restored_next_take[track_id] = max_take + 1
            self.current_take_number = restored_next_take

            self.comp_regions = {}
            for track_id_str, regions_data in dict(payload.get("comp_regions", {})).items():
                track_id = int(track_id_str)
                self.comp_regions[track_id] = [CompRegion(**region_data) for region_data in regions_data]

            self.next_comp_region_id = int(payload.get("next_comp_region_id", 1))
            if self.next_comp_region_id < 1:
                self.next_comp_region_id = 1

            for track_id in set(self.takes.keys()) | set(self.current_take_number.keys()) | set(self.comp_regions.keys()):
                self.ensure_track(track_id)

            return True
        except Exception as exc:
            print(f"Error restoring session snapshot payload: {exc}")
            return False
    
    def start_new_take(self, track_id: int) -> RecordingTake:
        """Start a new recording take on a track."""
        take_number = self.current_take_number.get(track_id, 1)
        
        take = RecordingTake(
            take_number=take_number,
            timestamp=datetime.now().isoformat(),
            track_id=track_id,
            duration_seconds=0.0,
            notes=""
        )
        
        if track_id not in self.takes:
            self.takes[track_id] = []
        
        self.takes[track_id].append(take)
        self.current_take_number[track_id] = take_number + 1
        self.total_takes += 1
        
        return take
    
    def finish_take(
        self,
        track_id: int,
        duration_seconds: float,
        level_stats: Dict[str, float],
        notes: str = "",
        start_sample: Optional[int] = None,
        end_sample: Optional[int] = None,
    ) -> Optional[RecordingTake]:
        """Finish current take, record stats."""
        if track_id not in self.takes or not self.takes[track_id]:
            return None
        
        take = self.takes[track_id][-1]
        take.duration_seconds = duration_seconds
        if start_sample is not None:
            take.start_sample = int(start_sample)
        if end_sample is not None:
            take.end_sample = int(end_sample)
        take.level_stats = level_stats
        take.notes = notes
        
        self.total_recording_time_seconds += duration_seconds
        
        # Push to undo stack
        self.undo_stack.append(take)
        if len(self.undo_stack) > self.max_undo_levels:
            self.undo_stack.pop(0)
        
        self.redo_stack.clear()
        
        return take
    
    def undo_last_take(self) -> Optional[RecordingTake]:
        """Undo last take (move to redo stack)."""
        if not self.undo_stack:
            return None
        
        take = self.undo_stack.pop()
        self.redo_stack.append(take)
        
        # Mark as unused
        take.used = False
        
        return take
    
    def redo_last_take(self) -> Optional[RecordingTake]:
        """Redo last undone take."""
        if not self.redo_stack:
            return None
        
        take = self.redo_stack.pop()
        self.undo_stack.append(take)
        
        # Mark as used
        take.used = True
        
        return take
    
    def get_active_takes(self) -> Dict[int, RecordingTake]:
        """Get currently active take for each track."""
        active = {}
        for track_id, takes in self.takes.items():
            # Find last used take
            for take in reversed(takes):
                if take.used:
                    active[track_id] = take
                    break
        return active
    
    def get_all_takes_for_track(self, track_id: int) -> List[RecordingTake]:
        """Get all takes for a track, sorted by take number."""
        if track_id not in self.takes:
            return []
        return sorted(self.takes[track_id], key=lambda t: t.take_number)

    def get_take(self, track_id: int, take_number: int) -> Optional[RecordingTake]:
        """Get one take by track and take number."""
        for take in self.get_all_takes_for_track(track_id):
            if take.take_number == take_number:
                return take
        return None

    def set_active_take(self, track_id: int, take_number: int) -> bool:
        """Mark one take active for a track and deactivate all others."""
        track_takes = self.get_all_takes_for_track(track_id)
        if not track_takes:
            return False

        found = False
        for take in track_takes:
            is_selected = take.take_number == take_number
            take.used = is_selected
            found = found or is_selected

        return found

    def set_take_keeper(self, track_id: int, take_number: int, is_keeper: bool) -> bool:
        take = self.get_take(track_id, take_number)
        if take is None:
            return False
        take.is_keeper = bool(is_keeper)
        return True

    def set_take_muted(self, track_id: int, take_number: int, is_muted: bool) -> bool:
        take = self.get_take(track_id, take_number)
        if take is None:
            return False
        take.is_muted = bool(is_muted)
        return True

    def set_take_rating(self, track_id: int, take_number: int, rating: int) -> bool:
        take = self.get_take(track_id, take_number)
        if take is None:
            return False
        take.rating = max(0, min(5, int(rating)))
        return True
    
    def delete_take(self, track_id: int, take_number: int) -> bool:
        """Delete a specific take."""
        if track_id not in self.takes:
            return False

        previous_count = len(self.takes[track_id])
        self.takes[track_id] = [
            t for t in self.takes[track_id]
            if t.take_number != take_number
        ]
        if len(self.takes[track_id]) == previous_count:
            return False

        # Ensure one active take remains when takes still exist.
        if self.takes[track_id] and not any(t.used for t in self.takes[track_id]):
            self.takes[track_id][-1].used = True

        return True
    
    def set_preset(self, preset: RecordingPreset) -> None:
        """Set recording preset."""
        self.preset = preset
    
    def save_session_metadata(self) -> bool:
        """Save session metadata to JSON."""
        try:
            metadata = {
                "session_id": self.session_id,
                "project_name": self.project_name,
                "created_at": self.created_at,
                "preset": asdict(self.preset),
                "ui_preferences": self.ui_preferences,
                "total_takes": self.total_takes,
                "total_recording_time_seconds": self.total_recording_time_seconds,
                "takes": {},
                "current_take_number": {str(track_id): int(next_take) for track_id, next_take in self.current_take_number.items()},
                "comp_regions": {},
                "next_comp_region_id": int(self.next_comp_region_id),
            }
            
            # Serialize takes
            for track_id, takes in self.takes.items():
                metadata["takes"][str(track_id)] = [asdict(t) for t in takes]
            for track_id, regions in self.comp_regions.items():
                metadata["comp_regions"][str(track_id)] = [asdict(region) for region in regions]
            
            session_file = self._recording_sessions_dir / f"{self.session_id}_metadata.json"
            
            with open(session_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving session metadata: {e}")
            return False
    
    @classmethod
    def load_session_metadata(cls, session_id: str) -> Optional['RecordingSession']:
        """Load session metadata from JSON."""
        try:
            session_file = ECHO_ROOT / "recording_sessions" / f"{session_id}_metadata.json"
            
            if not session_file.exists():
                return None
            
            with open(session_file, 'r') as f:
                metadata = json.load(f)
            
            session = cls(metadata["session_id"], metadata["project_name"])
            session.created_at = metadata["created_at"]
            session.total_takes = metadata["total_takes"]
            session.total_recording_time_seconds = metadata["total_recording_time_seconds"]
            
            # Deserialize preset
            preset_data = metadata.get("preset", {})
            session.preset = RecordingPreset(**preset_data)
            session.ui_preferences = dict(metadata.get("ui_preferences", session.ui_preferences))
            
            # Deserialize takes
            for track_id_str, takes_data in metadata.get("takes", {}).items():
                track_id = int(track_id_str)
                session.takes[track_id] = [RecordingTake(**t) for t in takes_data]

            session.current_take_number = {
                int(track_id_str): int(next_take)
                for track_id_str, next_take in metadata.get("current_take_number", {}).items()
            }
            for track_id, takes in session.takes.items():
                if track_id not in session.current_take_number:
                    max_take = max((int(take.take_number) for take in takes), default=0)
                    session.current_take_number[track_id] = max_take + 1

            session.comp_regions = {}
            for track_id_str, regions_data in metadata.get("comp_regions", {}).items():
                track_id = int(track_id_str)
                session.comp_regions[track_id] = [CompRegion(**region_data) for region_data in regions_data]

            session.next_comp_region_id = int(metadata.get("next_comp_region_id", 1))
            if session.next_comp_region_id < 1:
                session.next_comp_region_id = 1

            for track_id in set(session.takes.keys()) | set(session.current_take_number.keys()) | set(session.comp_regions.keys()):
                session.ensure_track(track_id)
            
            return session
        except Exception as e:
            print(f"Error loading session metadata: {e}")
            return None


class RecordingPresetManager:
    """Manage recording presets."""
    
    def __init__(self):
        self.presets: Dict[str, RecordingPreset] = {}
        self.presets_file = ECHO_ROOT / "recording_presets.json"
        self.load_presets()
    
    def load_presets(self) -> None:
        """Load presets from file."""
        if not self.presets_file.exists():
            self._create_default_presets()
            return
        
        try:
            with open(self.presets_file, 'r') as f:
                data = json.load(f)
            
            self.presets = {
                name: RecordingPreset(**preset_data)
                for name, preset_data in data.items()
            }
        except Exception as e:
            print(f"Error loading presets: {e}")
            self._create_default_presets()
    
    def save_presets(self) -> bool:
        """Save presets to file."""
        try:
            data = {name: asdict(preset) for name, preset in self.presets.items()}
            
            with open(self.presets_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving presets: {e}")
            return False
    
    def add_preset(self, preset: RecordingPreset) -> None:
        """Add or update a preset."""
        self.presets[preset.name] = preset
        self.save_presets()
    
    def get_preset(self, name: str) -> Optional[RecordingPreset]:
        """Get preset by name."""
        return self.presets.get(name)
    
    def list_presets(self) -> List[str]:
        """List all preset names."""
        return list(self.presets.keys())
    
    def delete_preset(self, name: str) -> bool:
        """Delete preset by name."""
        if name in self.presets and name != "Default":
            del self.presets[name]
            self.save_presets()
            return True
        return False
    
    def _create_default_presets(self) -> None:
        """Create default recording presets."""
        presets = [
            RecordingPreset(
                name="Podcast",
                num_tracks=2,
                sample_rate=44100,
                gain_db=-12.0,
                auto_gain=True,
                click_enabled=False,
                metronome_bpm=0
            ),
            RecordingPreset(
                name="Band Recording",
                num_tracks=8,
                sample_rate=48000,
                gain_db=0.0,
                auto_gain=False,
                click_enabled=True,
                click_volume_db=-12.0,
                metronome_bpm=120
            ),
            RecordingPreset(
                name="Vocal Track",
                num_tracks=1,
                sample_rate=44100,
                gain_db=-6.0,
                auto_gain=True,
                click_enabled=True,
                click_volume_db=-6.0,
                auto_punch_enabled=True,
                auto_punch_start_bars=1,
                auto_punch_duration_bars=4
            ),
            RecordingPreset(
                name="Studio (Professional)",
                num_tracks=16,
                sample_rate=96000,
                gain_db=0.0,
                auto_gain=False,
                click_enabled=True,
                click_volume_db=-20.0,
                metronome_bpm=120
            )
        ]
        
        for preset in presets:
            self.presets[preset.name] = preset
        
        self.save_presets()
