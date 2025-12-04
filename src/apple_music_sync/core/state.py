"""Export state management for incremental sync."""

import json
from datetime import datetime
from pathlib import Path

from ..models.state import ExportState, FileSignature, PlaylistSignature


class StateManager:
    """Manages export state for incremental sync."""

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state = self._load()

    def _load(self) -> ExportState:
        """Load state from file or create new state."""
        if not self.state_file.exists():
            return ExportState(
                library_path=Path("."),
                output_dir=self.state_file.parent,
            )

        try:
            with open(self.state_file) as f:
                data = json.load(f)
            return ExportState.from_dict(data)
        except Exception:
            # If corrupted, start fresh
            return ExportState(
                library_path=Path("."),
                output_dir=self.state_file.parent,
            )

    def save(self) -> None:
        """Save state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.state_file, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2)

    def get_file_signature(self, path: Path) -> FileSignature:
        """Get signature for a file."""
        stat = path.stat()
        return FileSignature(
            path=str(path),
            size=stat.st_size,
            mtime=stat.st_mtime,
        )

    def is_file_changed(self, path: Path) -> bool:
        """Check if file has changed since last export."""
        file_key = str(path)

        if file_key not in self.state.exported_files:
            return True

        stored_sig = self.state.exported_files[file_key]
        return stored_sig.is_changed(path)

    def update_file(self, path: Path) -> None:
        """Update file signature in state."""
        sig = self.get_file_signature(path)
        self.state.exported_files[sig.path] = sig

    def is_playlist_changed(self, name: str, track_ids: list[str]) -> bool:
        """Check if playlist has changed since last export."""
        import hashlib

        # Generate hash of track IDs
        track_ids_str = "".join(track_ids)
        current_hash = hashlib.md5(track_ids_str.encode()).hexdigest()

        if name not in self.state.exported_playlists:
            return True

        stored_sig = self.state.exported_playlists[name]
        return stored_sig.track_ids_hash != current_hash

    def update_playlist(self, name: str, track_ids: list[str]) -> None:
        """Update playlist signature in state."""
        import hashlib

        track_ids_str = "".join(track_ids)
        track_hash = hashlib.md5(track_ids_str.encode()).hexdigest()

        sig = PlaylistSignature(
            name=name,
            track_ids_hash=track_hash,
            track_count=len(track_ids),
        )
        self.state.exported_playlists[name] = sig

    def mark_export_complete(self, bytes_exported: int) -> None:
        """Mark export as complete and update statistics."""
        self.state.last_export = datetime.now()
        self.state.total_exports += 1
        self.state.total_bytes_exported += bytes_exported
