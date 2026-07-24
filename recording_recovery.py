"""
Echo Pro recording recovery snapshot helpers.
Provides atomic snapshot writes and strict validation before restore.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from app_paths import ECHO_ROOT


class RecoverySnapshotManager:
    """Manages crash-safe recording recovery snapshots per session."""

    def __init__(self, root_dir: Optional[Path] = None):
        base = root_dir or (ECHO_ROOT / "recording_recovery")
        self.root_dir = Path(base)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir = self.root_dir / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _snapshot_path(self, session_id: str) -> Path:
        safe_session = str(session_id).strip().replace(" ", "_")
        return self.root_dir / f"{safe_session}_snapshot.json"

    @staticmethod
    def _build_checksum(payload: Dict[str, object]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def write_snapshot(
        self,
        session_id: str,
        project_name: str,
        payload: Dict[str, object],
        reason: str,
        interrupted: bool,
    ) -> bool:
        """Write a snapshot atomically so partial files are never surfaced."""
        snapshot = {
            "version": 1,
            "session_id": str(session_id),
            "project_name": str(project_name),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reason": str(reason),
            "interrupted": bool(interrupted),
            "payload": payload,
        }
        snapshot["checksum"] = self._build_checksum(snapshot["payload"])

        target = self._snapshot_path(session_id)
        temp_path = target.with_suffix(".tmp")
        history_path = self._history_snapshot_path(session_id)
        history_temp_path = history_path.with_suffix(".tmp")
        try:
            temp_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
            temp_path.replace(target)
            history_temp_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
            history_temp_path.replace(history_path)
            return True
        except Exception:
            return False

    def _history_snapshot_path(self, session_id: str) -> Path:
        safe_session = str(session_id).strip().replace(" ", "_")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return self.history_dir / f"{safe_session}_{stamp}.json"

    def load_snapshot(self, session_id: str) -> Optional[Dict[str, object]]:
        target = self._snapshot_path(session_id)
        if not target.exists():
            return None
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            return None

    def clear_snapshot(self, session_id: str) -> bool:
        target = self._snapshot_path(session_id)
        if not target.exists():
            return True
        try:
            target.unlink()
            return True
        except Exception:
            return False

    def validate_snapshot(
        self,
        snapshot: Dict[str, object],
        expected_session_id: str,
        expected_project_name: str,
        max_age_hours: int = 24,
    ) -> Tuple[bool, str]:
        """Validate identity, freshness, and payload integrity before restore."""
        if not isinstance(snapshot, dict):
            return False, "Snapshot format is invalid"

        if int(snapshot.get("version", 0)) != 1:
            return False, "Snapshot version is unsupported"

        if str(snapshot.get("session_id", "")) != str(expected_session_id):
            return False, "Snapshot belongs to a different session"

        if str(snapshot.get("project_name", "")) != str(expected_project_name):
            return False, "Snapshot belongs to a different project"

        created_at = str(snapshot.get("created_at", ""))
        try:
            created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except Exception:
            return False, "Snapshot timestamp is invalid"

        now_utc = datetime.now(timezone.utc)
        created_utc = created_dt.astimezone(timezone.utc)
        age = now_utc - created_utc
        if age > timedelta(hours=max(1, int(max_age_hours))):
            return False, "Snapshot is too old"

        payload = snapshot.get("payload")
        if not isinstance(payload, dict):
            return False, "Snapshot payload is missing"

        checksum = str(snapshot.get("checksum", ""))
        if checksum != self._build_checksum(payload):
            return False, "Snapshot checksum mismatch"

        interrupted = snapshot.get("interrupted")
        if not isinstance(interrupted, bool):
            return False, "Snapshot interrupted flag is invalid"

        return True, "ok"

    def list_snapshot_history(self, session_id: str, limit: int = 20) -> list[Path]:
        safe_session = str(session_id).strip().replace(" ", "_")
        candidates = sorted(
            self.history_dir.glob(f"{safe_session}_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidates[: max(1, int(limit))]

    def load_snapshot_from_path(self, file_path: Path) -> Optional[Dict[str, object]]:
        path = Path(file_path)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
