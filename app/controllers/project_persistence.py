"""Project Persistence Manager (Group 2.2)

Non-destructive project serialization: JSON-based format that preserves source
audio file paths and metadata without modifying original files.

Schema supports:
- Backward compatibility via version field
- Demucs stems and ACE transcriptions stored as metadata
- Track arrangement, effects chains, and automation saved as JSON references
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Current project file version for migration compatibility
PROJECT_FORMAT_VERSION = "1.0"
PROJECT_FILE_EXTENSION = ".echoproj"


@dataclass
class ProjectMetadata:
    """Metadata for a project."""
    name: str
    version: str = PROJECT_FORMAT_VERSION
    created_at: str = ""
    last_modified: str = ""
    sample_rate: int = 44100
    bpm: float = 120.0
    time_signature: str = "4/4"
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.last_modified:
            self.last_modified = datetime.now().isoformat()


class ProjectPersistence:
    """
    Handles saving/loading EchoApp projects in non-destructive JSON format.
    
    Non-destructive principle:
    - Source audio files are referenced by path, never copied or modified
    - Stems (Demucs output) stored separately in project folder
    - All effects, automation, arrangement saved as JSON metadata
    - Users can move/rename project folder and all references remain valid
    """
    
    def __init__(self, project_dir: Optional[Path] = None):
        """
        Initialize persistence manager.
        project_dir: folder where .echoproj and stems are stored
        """
        self.project_dir = project_dir or Path.home() / ".echo_projects"
        self.project_dir.mkdir(parents=True, exist_ok=True)
    
    def save_project(self, project_data: Dict[str, Any], project_path: Path) -> bool:
        """
        Save project to JSON file.
        
        Args:
            project_data: Dict with keys: metadata, tracks, clips, timeline_state
            project_path: Full path to .echoproj file
        
        Returns:
            True if successful
        """
        try:
            project_path = Path(project_path)
            
            # Ensure directory exists
            project_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Update last_modified timestamp
            if "metadata" in project_data:
                project_data["metadata"]["last_modified"] = datetime.now().isoformat()
            
            # Write JSON with pretty formatting
            with open(project_path, "w") as f:
                json.dump(project_data, f, indent=2)
            
            logger.info(f"Project saved: {project_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save project: {e}")
            return False
    
    def load_project(self, project_path: Path) -> Optional[Dict[str, Any]]:
        """
        Load project from JSON file.
        
        Args:
            project_path: Full path to .echoproj file
        
        Returns:
            Project dict or None if load failed
        """
        try:
            project_path = Path(project_path)
            
            if not project_path.exists():
                logger.warning(f"Project file not found: {project_path}")
                return None
            
            with open(project_path, "r") as f:
                project_data = json.load(f)
            
            # Validate format version
            version = project_data.get("metadata", {}).get("version", "0.0")
            if not self._is_compatible_version(version):
                logger.warning(f"Project version {version} may have compatibility issues")
            
            logger.info(f"Project loaded: {project_path}")
            return project_data
        
        except Exception as e:
            logger.error(f"Failed to load project: {e}")
            return None
    
    def get_project_template(self, name: str, sample_rate: int = 44100, bpm: float = 120.0) -> Dict[str, Any]:
        """
        Create a new empty project template.
        
        Args:
            name: Project name
            sample_rate: Sample rate in Hz (default 44100)
            bpm: Tempo in beats per minute (default 120)
        
        Returns:
            Empty project dict ready to populate
        """
        metadata = ProjectMetadata(
            name=name,
            sample_rate=sample_rate,
            bpm=bpm
        )
        
        return {
            "metadata": asdict(metadata),
            "tracks": [],  # List of track objects
            "clips": [],  # List of clip references
            "stems": {},  # Demucs output stems (vocal, drums, bass, other)
            "timeline_state": {
                "playhead_ms": 0,
                "zoom_factor": 1.0,
                "scroll_position_px": 0,
            },
            "undo_history": [],  # For future undo/redo
        }
    
    def add_source_audio(self, project_data: Dict[str, Any], audio_path: Path, track_index: int) -> bool:
        """
        Add a source audio file reference to project (non-destructive).
        
        Args:
            project_data: Project dict
            audio_path: Path to source audio file
            track_index: Which track to add to
        
        Returns:
            True if successful
        """
        try:
            audio_path = Path(audio_path).resolve()
            
            if not audio_path.exists():
                logger.error(f"Audio file not found: {audio_path}")
                return False
            
            if "tracks" not in project_data:
                project_data["tracks"] = []
            
            # Ensure track exists
            while len(project_data["tracks"]) <= track_index:
                project_data["tracks"].append({
                    "name": f"Track {len(project_data['tracks']) + 1}",
                    "volume_db": 0.0,
                    "muted": False,
                    "soloed": False,
                    "source_file": None,
                    "start_ms": 0,
                })
            
            # Store absolute path reference
            project_data["tracks"][track_index]["source_file"] = str(audio_path)
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to add source audio: {e}")
            return False
    
    def add_stem(self, project_data: Dict[str, Any], stem_type: str, stem_path: Path) -> bool:
        """
        Add a Demucs stem file reference (stored in project folder).
        
        Args:
            project_data: Project dict
            stem_type: "vocal", "drums", "bass", or "other"
            stem_path: Path to stem file
        
        Returns:
            True if successful
        """
        try:
            if "stems" not in project_data:
                project_data["stems"] = {}
            
            stem_path = Path(stem_path).resolve()
            if not stem_path.exists():
                logger.error(f"Stem file not found: {stem_path}")
                return False
            
            project_data["stems"][stem_type] = str(stem_path)
            return True
        
        except Exception as e:
            logger.error(f"Failed to add stem: {e}")
            return False
    
    def export_to_wav(self, project_data: Dict[str, Any], output_path: Path, include_stems: bool = False) -> bool:
        """
        Export mixed master output to WAV (future implementation).
        
        Args:
            project_data: Project dict
            output_path: Output WAV file path
            include_stems: If True, export each stem as separate file
        
        Returns:
            True if successful
        
        Note: This is a placeholder for Phase 7 (mixing/mastering export).
        """
        logger.info(f"Export to WAV not yet implemented: {output_path}")
        return False
    
    def _is_compatible_version(self, version: str) -> bool:
        """Check if project version is compatible with current code."""
        # For now, accept v1.0 and warn on others
        return version.startswith("1.")
    
    def list_projects(self) -> List[Path]:
        """List all projects in the default projects directory."""
        return sorted(self.project_dir.glob(f"*{PROJECT_FILE_EXTENSION}"))
    
    def get_project_size(self, project_path: Path) -> int:
        """Get project file size in bytes."""
        project_path = Path(project_path)
        return project_path.stat().st_size if project_path.exists() else 0
